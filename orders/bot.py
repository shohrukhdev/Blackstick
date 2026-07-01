import logging
import secrets
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

LINK_TOKEN_TTL = 600  # 10 minutes

# ── Status labels ──────────────────────────────────────────────────────────

_STATUS_LABEL = {
    'SUBMITTED': '🕐 Kutilmoqda',
    'ACCEPTED': '✅ Qabul qilindi',
    'IN_SHIPMENT': '🚚 Yetkazilmoqda',
    'DELIVERED': '🎉 Yetkazildi',
    'DECLINED': '❌ Rad etildi',
}

# ── Keyboard builders (also imported by celery_tasks) ──────────────────────


def build_client_keyboard(site_url: str) -> ReplyKeyboardMarkup:
    shop_url = f'{site_url}/orders/client/'
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton('🛍 Katalog', web_app=WebAppInfo(url=shop_url))],
            [KeyboardButton('📦 Buyurtmalarim'), KeyboardButton('💰 Hisobim')],
            [KeyboardButton('📍 Joylashuvimni yangilash')],
        ],
        resize_keyboard=True,
    )


def build_supplier_keyboard(site_url: str) -> ReplyKeyboardMarkup:
    dash_url = f'{site_url}/orders/'
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton('📊 Dashboard', web_app=WebAppInfo(url=dash_url))],
            [KeyboardButton('📋 Yangi buyurtmalar'), KeyboardButton('👥 Mijozlar')],
        ],
        resize_keyboard=True,
    )


# ── Application factory ────────────────────────────────────────────────────


def get_application() -> Application:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is not configured')
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start_handler))
    app.add_handler(CommandHandler('help', help_handler))
    app.add_handler(CommandHandler('orders', orders_handler))
    app.add_handler(CommandHandler('balance', balance_handler))
    app.add_handler(CommandHandler('location', location_handler))
    app.add_handler(CommandHandler('unlink', unlink_handler))
    app.add_handler(CallbackQueryHandler(role_callback, pattern=r'^role:(client|supplier)$'))
    app.add_handler(MessageHandler(filters.LOCATION, save_location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_button_router))
    return app


# ── Token helpers ──────────────────────────────────────────────────────────


def make_link_token(telegram_id: int, role: str) -> str:
    """Store telegram_id in Redis keyed by role + random token. Returns the token."""
    token = secrets.token_urlsafe(32)
    cache.set(f'telegram:link:{role}:{token}', telegram_id, timeout=LINK_TOKEN_TTL)
    return token


# ── DB helpers (sync_to_async wrappers) ────────────────────────────────────


@sync_to_async
def _get_client_by_telegram(telegram_id: int):
    from orders.models import Client
    try:
        return Client.objects.select_related('user').get(telegram_id=telegram_id)
    except Client.DoesNotExist:
        return None


@sync_to_async
def _get_supplier_by_telegram(telegram_id: int):
    from orders.models import Supplier
    try:
        return Supplier.objects.select_related('user').get(telegram_id=telegram_id)
    except Supplier.DoesNotExist:
        return None


@sync_to_async
def _save_client_location(telegram_id: int, latitude: float, longitude: float) -> bool:
    from django.utils import timezone
    from orders.models import Client
    updated = Client.objects.filter(telegram_id=telegram_id).update(
        latitude=latitude,
        longitude=longitude,
        location_updated_at=timezone.now(),
    )
    return updated > 0


@sync_to_async
def _unlink_telegram(telegram_id: int) -> str:
    """Clear telegram_id from Client or Supplier. Returns 'client', 'supplier', or 'none'."""
    from orders.models import Client, Supplier
    if Client.objects.filter(telegram_id=telegram_id).update(telegram_id=None):
        return 'client'
    if Supplier.objects.filter(telegram_id=telegram_id).update(telegram_id=None):
        return 'supplier'
    return 'none'


@sync_to_async
def _get_client_active_orders(telegram_id: int):
    """Returns (client, orders_list) or (None, []) if not linked."""
    from orders.constants import OrderStatus
    from orders.models import Client
    from orders.services import get_client_orders
    try:
        client = Client.objects.select_related('user').get(telegram_id=telegram_id)
    except Client.DoesNotExist:
        return None, []
    orders = list(
        get_client_orders(
            client,
            statuses=[OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.IN_SHIPMENT],
        )
        .select_related('supplier')[:10]
    )
    return client, orders


@sync_to_async
def _get_supplier_pending_orders(telegram_id: int):
    """Returns (supplier, annotated_orders_list) or (None, []) if not linked."""
    from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Sum, Value, When
    from django.db.models.functions import Coalesce
    from orders.constants import OrderStatus
    from orders.models import Order, Supplier

    try:
        supplier = Supplier.objects.get(telegram_id=telegram_id)
    except Supplier.DoesNotExist:
        return None, []

    eff_price = Case(
        When(order_items__adjusted_retail_price__isnull=False, then=F('order_items__adjusted_retail_price')),
        default=F('order_items__retail_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    line_total = ExpressionWrapper(
        eff_price * F('order_items__quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    orders = list(
        Order.objects
        .filter(supplier=supplier, status__in=[OrderStatus.SUBMITTED, OrderStatus.ACCEPTED])
        .select_related('client')
        .annotate(
            item_count=Count('order_items', distinct=True),
            order_total=Coalesce(
                Sum(line_total), Value(Decimal('0')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-submitted_at')[:10]
    )
    return supplier, orders


@sync_to_async
def _get_client_balance_data(telegram_id: int):
    """Returns (client, [(supplier, balance_dict, recent_payments)]) or (None, [])."""
    from orders.models import Client, PaymentRecord
    from orders.services import get_client_balance

    try:
        client = Client.objects.get(telegram_id=telegram_id)
    except Client.DoesNotExist:
        return None, []

    supplier_links = list(
        client.supplier_links.filter(is_active=True).select_related('supplier')
    )
    results = []
    for sc in supplier_links:
        supplier = sc.supplier
        balance = get_client_balance(supplier, client)
        recent_payments = list(
            PaymentRecord.objects
            .filter(supplier=supplier, client=client)
            .order_by('-date', '-created_at')[:3]
        )
        results.append((supplier, balance, recent_payments))
    return client, results


@sync_to_async
def _get_supplier_clients_outstanding(telegram_id: int):
    """Returns (supplier, [(company_name, pending_total)]) sorted by outstanding desc."""
    from django.db.models import Case, DecimalField, ExpressionWrapper, F, Sum, Value, When
    from django.db.models.functions import Coalesce
    from orders.constants import OrderStatus, PaymentStatus
    from orders.models import OrderItem, Supplier

    try:
        supplier = Supplier.objects.get(telegram_id=telegram_id)
    except Supplier.DoesNotExist:
        return None, []

    eff_price = Case(
        When(adjusted_retail_price__isnull=False, then=F('adjusted_retail_price')),
        default=F('retail_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    line_total = ExpressionWrapper(
        eff_price * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    rows = list(
        OrderItem.objects
        .filter(
            order__supplier=supplier,
            order__status=OrderStatus.DELIVERED,
            order__payment_status=PaymentStatus.PENDING,
        )
        .values('order__client__company_name', 'order__client_id')
        .annotate(
            pending_total=Coalesce(
                Sum(line_total), Value(Decimal('0')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by('-pending_total')[:5]
    )
    return supplier, [(r['order__client__company_name'], r['pending_total']) for r in rows]


# ── Handlers ───────────────────────────────────────────────────────────────


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    site = settings.SITE_URL.rstrip('/')

    client = await _get_client_by_telegram(telegram_id)
    if client:
        await update.message.reply_text(
            f'Xush kelibsiz, <b>{client.company_name}</b>! 👋\n\n'
            f'Quyidagi tugmalar orqali ishlashingiz mumkin:\n'
            f'• 🛍 <b>Katalog</b> — buyurtma berish\n'
            f'• 📦 <b>Buyurtmalarim</b> — faol buyurtmalar holati\n'
            f'• 💰 <b>Hisobim</b> — balans va so\'nggi to\'lovlar\n'
            f'• 📍 <b>Joylashuvimni yangilash</b> — yetkazib berish manzili\n\n'
            f'Barcha buyruqlar: /help',
            reply_markup=build_client_keyboard(site),
            parse_mode='HTML',
        )
        return

    supplier = await _get_supplier_by_telegram(telegram_id)
    if supplier:
        await update.message.reply_text(
            f'Xush kelibsiz, <b>{supplier.business_name}</b>! 👋\n\n'
            f'Quyidagi tugmalar orqali ishlashingiz mumkin:\n'
            f'• 📊 <b>Dashboard</b> — boshqaruv paneli\n'
            f'• 📋 <b>Yangi buyurtmalar</b> — kutilayotgan buyurtmalar\n'
            f'• 👥 <b>Mijozlar</b> — qoldiq bo\'yicha mijozlar ro\'yxati\n\n'
            f'Barcha buyruqlar: /help',
            reply_markup=build_supplier_keyboard(site),
            parse_mode='HTML',
        )
        return

    # Unlinked user — show role chooser
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton('🛒 Mijoz', callback_data='role:client'),
        InlineKeyboardButton('🏭 Ta\'minotchi', callback_data='role:supplier'),
    ]])
    await update.message.reply_text(
        'Assalomu alaykum! Siz qanday foydalanuvchisiz?',
        reply_markup=keyboard,
    )


async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    role = query.data.split(':')[1]  # 'client' or 'supplier'
    token = make_link_token(telegram_id, role)
    site = settings.SITE_URL.rstrip('/')

    if role == 'client':
        link_url = f'{site}/orders/client/link-telegram/?token={token}'
        label = "Mijoz hisobini bog'lash"
        instructions = (
            "Hisobingizni bog'lash uchun quyidagi tugmani bosing.\n\n"
            "Agar hali ro'yxatdan o'tmagan bo'lsangiz, "
            "avval ta'minotchingizdan ro'yxatdan o'tish havolasini so'rang."
        )
    else:
        link_url = f'{site}/orders/link-telegram/?token={token}'
        label = "Ta'minotchi hisobini bog'lash"
        instructions = (
            "Hisobingizni bog'lash uchun quyidagi tugmani bosing.\n\n"
            "Tizimga kirganingizdan so'ng Telegram hisobingiz avtomatik bog'lanadi."
        )

    link_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f'🔗 {label}', url=link_url)
    ]])
    await query.edit_message_text(
        f'{instructions}\n\n⏱ Havola 10 daqiqa amal qiladi.',
        reply_markup=link_keyboard,
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '<b>Mavjud buyruqlar:</b>\n\n'
        '/start — Bosh menyu\n'
        '/orders — Faol buyurtmalar (mijoz) / Yangi buyurtmalar (ta\'minotchi)\n'
        '/balance — Balans va so\'nggi to\'lovlar (faqat mijozlar)\n'
        '/location — Yetkazib berish manzilini yangilash\n'
        '/unlink — Telegram hisobini uzish\n'
        '/help — Ushbu yordam xabari',
        parse_mode='HTML',
    )


async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    client, orders = await _get_client_active_orders(telegram_id)
    if client is not None:
        if not orders:
            site = settings.SITE_URL.rstrip('/')
            await update.message.reply_text(
                'Hozirda faol buyurtmalar yo\'q.\nKatalogdan buyurtma bering 👇',
                reply_markup=build_client_keyboard(site),
            )
            return
        lines = ['<b>📦 Faol buyurtmalaringiz:</b>\n']
        for o in orders:
            status_label = _STATUS_LABEL.get(o.status, o.status)
            date_str = o.submitted_at.strftime('%d.%m.%Y') if o.submitted_at else '—'
            lines.append(
                f'• #{o.id} — {status_label}\n'
                f'  📅 {date_str} · {o.item_count} ta tovar · {o.order_total:,.0f} so\'m'
            )
        await update.message.reply_text('\n'.join(lines), parse_mode='HTML')
        return

    supplier, orders = await _get_supplier_pending_orders(telegram_id)
    if supplier is not None:
        if not orders:
            await update.message.reply_text('Hozirda yangi buyurtmalar yo\'q.')
            return
        lines = [f'<b>📋 Yangi buyurtmalar ({len(orders)} ta):</b>\n']
        for i, o in enumerate(orders, 1):
            status_label = _STATUS_LABEL.get(o.status, o.status)
            lines.append(
                f'{i}. <b>{o.client.company_name}</b> — {o.item_count} ta · '
                f'{o.order_total:,.0f} so\'m [{status_label}]'
            )
        await update.message.reply_text('\n'.join(lines), parse_mode='HTML')
        return

    await update.message.reply_text(
        "Hisobingiz topilmadi. /start buyrug'ini yuborib hisobingizni bog'lang."
    )


async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    supplier = await _get_supplier_by_telegram(telegram_id)
    if supplier:
        await update.message.reply_text("Bu funksiya faqat mijozlar uchun.")
        return

    client, results = await _get_client_balance_data(telegram_id)
    if client is None:
        await update.message.reply_text(
            "Hisobingiz topilmadi. /start buyrug'ini yuborib hisobingizni bog'lang."
        )
        return

    if not results:
        await update.message.reply_text("Siz hali hech qanday ta'minotchi bilan bog'lanmagansiz.")
        return

    lines = ['<b>💰 Hisobingiz:</b>\n']
    for sup, balance, payments in results:
        deposited = balance['deposited']
        settled = balance['settled']
        available = balance['balance']
        pending = balance['pending_total']

        lines.append(f"<b>Ta'minotchi: {sup.business_name}</b>")
        lines.append('━━━━━━━━━━━━━━━━━━')
        lines.append(f"Kiritilgan:  <b>{deposited:,.0f} so'm</b>")
        lines.append(f"Sarflangan:  {settled:,.0f} so'm")
        lines.append(f"Qoldiq:      <b>{available:,.0f} so'm</b>")
        if pending > 0:
            lines.append(f"To'lanmagan: <b>{pending:,.0f} so'm</b>")

        if payments:
            lines.append("\nSo'nggi to'lovlar:")
            for p in payments:
                date_str = p.date.strftime('%d.%m.%Y')
                lines.append(f"  + {p.amount:,.0f} so'm — {date_str}")
        lines.append('')

    await update.message.reply_text('\n'.join(lines), parse_mode='HTML')


async def clients_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    supplier, top_clients = await _get_supplier_clients_outstanding(telegram_id)

    if supplier is None:
        await update.message.reply_text(
            "Hisobingiz topilmadi. /start buyrug'ini yuborib hisobingizni bog'lang."
        )
        return

    if not top_clients:
        await update.message.reply_text('Barcha mijozlarning hisob-kitoblari tozalangan. ✅')
        return

    lines = ['<b>👥 Qoldiq bo\'yicha mijozlar:</b>\n']
    for i, (company_name, outstanding) in enumerate(top_clients, 1):
        lines.append(f"{i}. <b>{company_name}</b> — {outstanding:,.0f} so'm qoldiq")

    await update.message.reply_text('\n'.join(lines), parse_mode='HTML')


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton('📍 Joylashuvni yuborish', request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        'Yetkazib berish manzilini yuborish uchun quyidagi tugmani bosing:',
        reply_markup=reply_markup,
    )


async def save_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    location = update.message.location
    saved = await _save_client_location(telegram_id, location.latitude, location.longitude)
    site = settings.SITE_URL.rstrip('/')
    if saved:
        client = await _get_client_by_telegram(telegram_id)
        keyboard = build_client_keyboard(site) if client else ReplyKeyboardRemove()
        await update.message.reply_text('✅ Joylashuvingiz saqlandi!', reply_markup=keyboard)
    else:
        await update.message.reply_text(
            "Hisobingiz topilmadi. Avval /start buyrug'ini yuboring.",
            reply_markup=ReplyKeyboardRemove(),
        )


async def unlink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    result = await _unlink_telegram(telegram_id)
    if result == 'none':
        await update.message.reply_text(
            "Hisobingiz allaqachon bog'liq emas.\n/start bilan qaytadan ulashingiz mumkin.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        role_label = 'Mijoz' if result == 'client' else "Ta'minotchi"
        await update.message.reply_text(
            f"✅ {role_label} hisobingiz Telegram'dan uzildi.\n\n"
            "Qaytadan ulash uchun /start buyrug'ini yuboring.",
            reply_markup=ReplyKeyboardRemove(),
        )


_BUTTON_MAP = {
    '📦 Buyurtmalarim': orders_handler,
    '💰 Hisobim': balance_handler,
    '📍 Joylashuvimni yangilash': location_handler,
    '📋 Yangi buyurtmalar': orders_handler,
    '👥 Mijozlar': clients_summary_handler,
}


async def text_button_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    handler = _BUTTON_MAP.get(update.message.text)
    if handler:
        await handler(update, context)
