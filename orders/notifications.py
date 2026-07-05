import logging
from decimal import Decimal

from django.db.models import Case, DecimalField, ExpressionWrapper, F, Sum, Value, When
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)


def _order_total(order) -> Decimal:
    """Effective order total: adjusted price when set, otherwise original snapshot."""
    eff_price = Case(
        When(adjusted_retail_price__isnull=False, then=F('adjusted_retail_price')),
        default=F('retail_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    line = ExpressionWrapper(
        eff_price * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    result = order.order_items.aggregate(
        total=Coalesce(
            Sum(line), Value(Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    return result['total']


def _fmt(amount: Decimal) -> str:
    return f"{amount:,.0f} so'm"


def notify_supplier_new_order(order):
    from orders.celery_tasks import send_telegram_notification
    if not order.supplier.telegram_id:
        return
    total = _order_total(order)
    item_count = order.order_items.count()
    text = (
        f'📦 <b>Yangi buyurtma!</b>\n\n'
        f'Mijoz: <b>{order.client.company_name}</b>\n'
        f'Tovarlar: {item_count} ta\n'
        f'Jami: <b>{_fmt(total)}</b>\n\n'
        f"Batafsil ko'rish: /orders"
    )
    send_telegram_notification.delay(order.supplier.telegram_id, text)


def notify_client_order_accepted(order):
    from orders.celery_tasks import send_telegram_notification
    if not order.client.telegram_id:
        return
    total = _order_total(order)
    text = (
        f'✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n'
        f'Buyurtma #{order.id}\n'
        f'Jami: <b>{_fmt(total)}</b>\n\n'
        f'Holat: /orders'
    )
    send_telegram_notification.delay(order.client.telegram_id, text)


def notify_client_order_declined(order):
    from orders.celery_tasks import send_telegram_notification
    if not order.client.telegram_id:
        return
    note = order.supplier_note or "ko'rsatilmagan"
    text = (
        f'❌ <b>Buyurtmangiz rad etildi.</b>\n\n'
        f'Buyurtma #{order.id}\n'
        f'Sabab: {note}\n\n'
        f'Batafsil: /orders'
    )
    send_telegram_notification.delay(order.client.telegram_id, text)


def notify_client_prices_adjusted(order):
    from orders.celery_tasks import send_telegram_notification
    if not order.client.telegram_id:
        return
    total = _order_total(order)
    text = (
        f'⚠️ <b>Buyurtma narxlari yangilandi.</b>\n\n'
        f'Buyurtma #{order.id}\n'
        f'Yangilangan jami: <b>{_fmt(total)}</b>\n\n'
        f"Ko'rish: /orders"
    )
    send_telegram_notification.delay(order.client.telegram_id, text)


def notify_client_order_dispatched(order):
    from orders.celery_tasks import send_telegram_notification
    if not order.client.telegram_id:
        return
    text = (
        f"🚚 <b>Buyurtmangiz yo'lda!</b>\n\n"
        f"Buyurtma #{order.id} jo'natildi.\n"
        f'Yetkazilgach xabar beramiz.'
    )
    send_telegram_notification.delay(order.client.telegram_id, text)


def notify_client_order_delivered(order):
    from orders.celery_tasks import send_telegram_notification
    if not order.client.telegram_id:
        return
    total = _order_total(order)
    text = (
        f'🎉 <b>Buyurtmangiz yetkazildi!</b>\n\n'
        f'Buyurtma #{order.id}\n'
        f'Jami: <b>{_fmt(total)}</b>\n\n'
        f'Hisobingiz: /balance'
    )
    send_telegram_notification.delay(order.client.telegram_id, text)


def notify_client_payment_received(client, amount: Decimal, balance_after: Decimal, supplier_name: str):
    from orders.celery_tasks import send_telegram_notification
    if not client.telegram_id:
        return
    text = (
        f"💳 <b>Hisobingizga to'lov qo'shildi!</b>\n\n"
        f"Ta'minotchi: <b>{supplier_name}</b>\n"
        f"Miqdor: <b>{_fmt(amount)}</b>\n"
        f"Joriy balans: <b>{_fmt(balance_after)}</b>\n\n"
        f"Batafsil: /balance"
    )
    send_telegram_notification.delay(client.telegram_id, text)


def notify_supplier_client_payment(supplier, client, amount: Decimal, balance_after: Decimal):
    """Notify supplier that a payment was recorded (confirmation)."""
    from orders.celery_tasks import send_telegram_notification
    if not supplier.telegram_id:
        return
    text = (
        f"✅ <b>To'lov qayd etildi</b>\n\n"
        f"Mijoz: <b>{client.company_name}</b>\n"
        f"Miqdor: <b>{_fmt(amount)}</b>\n"
        f"Joriy balans: <b>{_fmt(balance_after)}</b>"
    )
    send_telegram_notification.delay(supplier.telegram_id, text)
