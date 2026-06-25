import logging
import secrets

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

LINK_TOKEN_TTL = 600  # 10 minutes


def get_application() -> Application:
    """Build and return the PTB Application (singleton-safe via module-level cache)."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is not configured')
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start_handler))
    app.add_handler(CommandHandler('location', location_handler))
    app.add_handler(CommandHandler('shop', shop_handler))
    app.add_handler(CommandHandler('dashboard', dashboard_handler))
    app.add_handler(MessageHandler(filters.LOCATION, save_location_handler))
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_link_token(telegram_id: int) -> str:
    token = secrets.token_urlsafe(32)
    cache.set(f'telegram:link:{token}', telegram_id, timeout=LINK_TOKEN_TTL)
    return token


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    client = await _get_client_by_telegram(telegram_id)
    supplier = await _get_supplier_by_telegram(telegram_id)

    if client:
        site = settings.SITE_URL.rstrip('/')
        shop_url = f'{site}/orders/client/'
        keyboard = [[KeyboardButton('🛍 Katalog', web_app=WebAppInfo(url=shop_url))]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f'Xush kelibsiz, {client.company_name}! Quyidagi tugmani bosib buyurtma bering.',
            reply_markup=reply_markup,
        )
    elif supplier:
        site = settings.SITE_URL.rstrip('/')
        dash_url = f'{site}/orders/'
        keyboard = [[KeyboardButton('📊 Dashboard', web_app=WebAppInfo(url=dash_url))]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f'Xush kelibsiz, {supplier.business_name}!',
            reply_markup=reply_markup,
        )
    else:
        token = _make_link_token(telegram_id)
        site = settings.SITE_URL.rstrip('/')
        link_url = f'{site}/orders/client/link-telegram/?token={token}'
        await update.message.reply_text(
            'Assalomu alaykum! Hisobingizni bog\'lash uchun quyidagi havolaga o\'ting:\n'
            f'{link_url}\n\n'
            'Havola 10 daqiqa amal qiladi.',
            reply_markup=ReplyKeyboardRemove(),
        )


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
    if saved:
        await update.message.reply_text(
            '✅ Joylashuvingiz saqlandi!',
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text(
            'Hisobingiz topilmadi. Avval /start buyrug\'ini yuboring va hisobingizni bog\'lang.',
            reply_markup=ReplyKeyboardRemove(),
        )


async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    client = await _get_client_by_telegram(telegram_id)
    if not client:
        await update.message.reply_text(
            'Siz mijoz sifatida ro\'yxatdan o\'tmagansiz. /start buyrug\'ini yuboring.'
        )
        return
    site = settings.SITE_URL.rstrip('/')
    shop_url = f'{site}/orders/client/'
    keyboard = [[KeyboardButton('🛍 Do\'konga o\'tish', web_app=WebAppInfo(url=shop_url))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Do\'konga o\'tish:', reply_markup=reply_markup)


async def dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    supplier = await _get_supplier_by_telegram(telegram_id)
    if not supplier:
        await update.message.reply_text(
            'Siz ta\'minotchi sifatida ro\'yxatdan o\'tmagansiz. /start buyrug\'ini yuboring.'
        )
        return
    site = settings.SITE_URL.rstrip('/')
    dash_url = f'{site}/orders/'
    keyboard = [[KeyboardButton('📊 Dashboardga o\'tish', web_app=WebAppInfo(url=dash_url))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Dashboardga o\'tish:', reply_markup=reply_markup)
