import logging

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def generate_order_invoice(order, invoice):
    """Render invoice_order.html for the given order and return PDF bytes."""
    from weasyprint import HTML

    from orders.models import Order

    order = (
        Order.objects
        .select_related('supplier', 'client')
        .prefetch_related('order_items', 'payment_records')
        .get(pk=order.pk)
    )

    logo_path = None
    if order.supplier.logo:
        try:
            logo_path = f'file://{order.supplier.logo.path}'
        except NotImplementedError:
            logo_path = None

    order_items = list(order.order_items.all())
    payments = list(order.payment_records.all().order_by('date'))

    html_string = render_to_string('orders/pdf/invoice_order.html', {
        'order': order,
        'invoice': invoice,
        'supplier': order.supplier,
        'client': order.client,
        'order_items': order_items,
        'payments': payments,
        'logo_path': logo_path,
    })

    return HTML(string=html_string).write_pdf()


def generate_payment_receipt(payment, invoice):
    """Render receipt_payment.html for the given PaymentRecord and return PDF bytes."""
    from weasyprint import HTML

    from orders.models import PaymentRecord

    payment = (
        PaymentRecord.objects
        .select_related('supplier', 'client', 'order', 'created_by')
        .get(pk=payment.pk)
    )

    logo_path = None
    if payment.supplier.logo:
        try:
            logo_path = f'file://{payment.supplier.logo.path}'
        except NotImplementedError:
            logo_path = None

    balance_after = payment.balance_after
    balance_before = (balance_after - payment.amount) if balance_after is not None else None

    html_string = render_to_string('orders/pdf/receipt_payment.html', {
        'payment': payment,
        'invoice': invoice,
        'supplier': payment.supplier,
        'client': payment.client,
        'logo_path': logo_path,
        'balance_before': balance_before,
        'balance_after': balance_after,
    })

    return HTML(string=html_string).write_pdf()
