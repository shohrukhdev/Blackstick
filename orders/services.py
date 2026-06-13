import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import (
    Case, Count, DecimalField, ExpressionWrapper, F, Max, Prefetch, Q, Sum, Value, When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from orders.constants import DeliveryStatus, OrderStatus, PaymentStatus, ShipmentStatus
from orders.models import (
    Category, Client, ClientInvite, Expense, Item, Order, OrderItem,
    PaymentRecord, Shipment, ShipmentOrder, SupplierClient,
)

logger = logging.getLogger(__name__)


# ── Catalog ────────────────────────────────────────────────────────────────


def get_client_catalog(supplier):
    """
    Client-facing catalog: ACTIVE items only, ordered by name.
    Returns (categories_qs, uncategorised_qs). Total: 3 queries.
    """
    active_items_qs = Item.objects.filter(is_active=True).order_by('name')
    categories = (
        Category.objects
        .filter(supplier=supplier)
        .prefetch_related(Prefetch('items', queryset=active_items_qs, to_attr='active_items'))
        .order_by('display_order', 'name')
    )
    uncategorised = Item.objects.filter(supplier=supplier, is_active=True, category=None).order_by('name')
    return categories, uncategorised


def get_supplier_catalog(supplier):
    """
    Returns (categories_qs, uncategorised_items_qs).
    Categories have `all_items` prefetched (active and inactive).
    Active items first, then inactive; alphabetical within each group.
    Total: 3 queries regardless of item/category count.
    """
    all_items_qs = Item.objects.order_by('-is_active', 'name')
    categories = (
        Category.objects
        .filter(supplier=supplier)
        .prefetch_related(Prefetch('items', queryset=all_items_qs, to_attr='all_items'))
        .order_by('display_order', 'name')
    )
    uncategorised = (
        Item.objects
        .filter(supplier=supplier, category=None)
        .order_by('-is_active', 'name')
    )
    return categories, uncategorised


def create_category(supplier, name, display_order=0):
    return Category.objects.create(supplier=supplier, name=name, display_order=display_order)


def update_category(category, **kwargs):
    for key, value in kwargs.items():
        setattr(category, key, value)
    category.save()
    return category


def delete_category(category):
    """Remove category; its items become uncategorised (category=None)."""
    category.items.update(category=None)
    category.delete()


def archive_item(item):
    item.is_active = False
    item.save(update_fields=['is_active', 'updated_at'])
    return item


def reactivate_item(item):
    item.is_active = True
    item.save(update_fields=['is_active', 'updated_at'])
    return item


# ── Clients ────────────────────────────────────────────────────────────────


def get_supplier_clients(supplier):
    """Returns SupplierClient qs for all active clients of this supplier."""
    return (
        SupplierClient.objects
        .filter(supplier=supplier, is_active=True)
        .select_related('client', 'client__user')
        .order_by('client__company_name')
    )


def get_active_invites(supplier):
    return (
        ClientInvite.objects
        .filter(supplier=supplier, is_used=False)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .order_by('-created_at')
    )


@transaction.atomic
def create_client_manually(supplier, company_name, phone, full_name, password, email=''):
    """Create a Django User + Client + SupplierClient link in one transaction."""
    base = (email or phone).strip()
    username = base if base else f'client_{uuid.uuid4().hex[:8]}'
    if User.objects.filter(username=username).exists():
        username = f'{username}_{uuid.uuid4().hex[:4]}'
    user = User.objects.create_user(
        username=username, password=password,
        email=email or '', first_name=full_name,
    )
    client = Client.objects.create(user=user, company_name=company_name, phone=phone)
    SupplierClient.objects.create(supplier=supplier, client=client)
    return client


def generate_invite(supplier, expires_days=30):
    return ClientInvite.objects.create(
        supplier=supplier,
        expires_at=timezone.now() + timedelta(days=expires_days),
    )


def get_client_orders(client, supplier=None, statuses=None):
    """
    Return annotated Order queryset for the given client (excludes DRAFTs).
    order_total uses effective retail price (adjusted when set, else snapshot).
    """
    effective_price = Case(
        When(
            order_items__adjusted_retail_price__isnull=False,
            then=F('order_items__adjusted_retail_price'),
        ),
        default=F('order_items__retail_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    line_total = ExpressionWrapper(
        effective_price * F('order_items__quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    qs = (
        Order.objects
        .filter(client=client)
        .exclude(status=OrderStatus.DRAFT)
        .select_related('supplier')
        .annotate(
            item_count=Count('order_items', distinct=True),
            order_total=Coalesce(
                Sum(line_total),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-submitted_at')
    )
    if supplier is not None:
        qs = qs.filter(supplier=supplier)
    if statuses is not None:
        qs = qs.filter(status__in=statuses)
    return qs


# ── Orders ────────────────────────────────────────────────────────────────


@transaction.atomic
def submit_order(client, supplier, cart_items, notes=''):
    """
    Create Order (SUBMITTED) + OrderItems with price snapshots.
    cart_items: [{'item_id': int, 'quantity': Decimal}]
    Raises ValueError if cart is empty or any item is invalid/inactive.
    """
    from orders import notifications

    if not cart_items:
        raise ValueError("Savat bo'sh. Kamida bitta tovar tanlang.")

    item_ids = [ci['item_id'] for ci in cart_items]
    items_map = {
        item.pk: item
        for item in Item.objects.filter(pk__in=item_ids, supplier=supplier, is_active=True)
    }

    invalid = [iid for iid in item_ids if iid not in items_map]
    if invalid:
        raise ValueError("Ba'zi tovarlar mavjud emas yoki faol emas.")

    order = Order.objects.create(
        supplier=supplier,
        client=client,
        status=OrderStatus.SUBMITTED,
        notes=notes,
        submitted_at=timezone.now(),
    )

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            item=items_map[ci['item_id']],
            item_name=items_map[ci['item_id']].name,
            item_unit=items_map[ci['item_id']].unit,
            quantity=Decimal(str(ci['quantity'])),
            retail_price=items_map[ci['item_id']].retail_price,
            base_price_snapshot=items_map[ci['item_id']].base_price,
            profit_snapshot=items_map[ci['item_id']].profit,
        )
        for ci in cart_items
    ])

    notifications.notify_supplier_new_order(order)
    return order


def update_order_note(order, note):
    """Persist supplier_note on any non-DRAFT order. No status restriction."""
    order.supplier_note = note.strip()
    order.save(update_fields=['supplier_note'])
    return order


@transaction.atomic
def accept_order(order, actor):
    """Set order status to ACCEPTED. Raises ValueError if not currently SUBMITTED."""
    from orders import notifications
    if order.status != OrderStatus.SUBMITTED:
        raise ValueError("Faqat yuborilgan buyurtmani qabul qilish mumkin.")
    order.status = OrderStatus.ACCEPTED
    order.accepted_at = timezone.now()
    order.save(update_fields=['status', 'accepted_at'])
    notifications.notify_client_order_accepted(order)
    return order


@transaction.atomic
def decline_order(order, actor, note=''):
    """Set order status to DECLINED. Raises ValueError if not currently SUBMITTED."""
    from orders import notifications
    if order.status != OrderStatus.SUBMITTED:
        raise ValueError("Faqat yuborilgan buyurtmani rad etish mumkin.")
    order.status = OrderStatus.DECLINED
    order.supplier_note = note
    order.save(update_fields=['status', 'supplier_note'])
    notifications.notify_client_order_declined(order)
    return order


@transaction.atomic
def adjust_order_item_price(order_item, new_retail_price, actor):
    """
    Set order_item.adjusted_retail_price. Marks order.prices_adjusted=True.
    Raises ValueError if order is not ACCEPTED or price is not positive.
    """
    from orders import notifications
    if order_item.order.status != OrderStatus.ACCEPTED:
        raise ValueError("Narxni faqat qabul qilingan buyurtmada o'zgartirish mumkin.")
    if new_retail_price <= 0:
        raise ValueError("Narx musbat son bo'lishi kerak.")

    was_first = not order_item.order.prices_adjusted

    order_item.adjusted_retail_price = new_retail_price
    order_item.save(update_fields=['adjusted_retail_price'])

    Order.objects.filter(pk=order_item.order_id).update(
        prices_adjusted=True,
        updated_at=timezone.now(),
    )

    if was_first:
        notifications.notify_client_prices_adjusted(order_item.order)

    return order_item


# ── Shipments ─────────────────────────────────────────────────────────────


def create_shipment(supplier, scheduled_date=None, notes=''):
    return Shipment.objects.create(
        supplier=supplier,
        scheduled_date=scheduled_date,
        notes=notes,
        status=ShipmentStatus.PREPARING,
    )


@transaction.atomic
def create_shipment_with_orders(supplier, order_ids, scheduled_date=None, notes=''):
    """Create a shipment and immediately assign orders atomically. Requires at least one order."""
    if not order_ids:
        raise ValueError("Kamida bitta buyurtma tanlang.")
    shipment = create_shipment(supplier, scheduled_date=scheduled_date, notes=notes)
    add_orders_to_shipment(shipment, order_ids)
    return shipment


@transaction.atomic
def add_orders_to_shipment(shipment, order_ids):
    """
    Assign ACCEPTED orders to a shipment. Each order must belong to the shipment's
    supplier and must not already be in an active shipment.
    Transitions Order.status → IN_SHIPMENT.
    Returns list of created ShipmentOrder instances.
    """
    supplier = shipment.supplier
    orders = list(
        Order.objects.filter(pk__in=order_ids, supplier=supplier, status=OrderStatus.ACCEPTED)
        .select_related('supplier')
    )
    if len(orders) != len(order_ids):
        raise ValueError("Ba'zi buyurtmalar mavjud emas yoki qabul qilingan emas.")

    # Prevent an order from being assigned to two active shipments
    already_assigned = ShipmentOrder.objects.filter(
        order__in=orders,
    ).exclude(delivery_status=DeliveryStatus.DELIVERED).values_list('order_id', flat=True)
    if already_assigned:
        raise ValueError("Ba'zi buyurtmalar allaqachon boshqa jo'natmada.")

    shipment_orders = ShipmentOrder.objects.bulk_create([
        ShipmentOrder(
            shipment=shipment,
            order=order,
            delivery_status=DeliveryStatus.PENDING,
        )
        for order in orders
    ])
    Order.objects.filter(pk__in=order_ids).update(status=OrderStatus.IN_SHIPMENT)
    return shipment_orders


@transaction.atomic
def update_shipment_order_status(shipment_order, new_status, actor):
    """
    Set a ShipmentOrder to any valid delivery status (bidirectional — allows correcting mistakes).
    Syncs parent Order.status and Shipment.status accordingly.
    """
    from orders import notifications

    valid = {DeliveryStatus.PENDING, DeliveryStatus.DISPATCHED, DeliveryStatus.DELIVERED}
    if new_status not in valid:
        raise ValueError(f"Noto'g'ri holat: '{new_status}'.")

    old_status = shipment_order.delivery_status
    if old_status == new_status:
        return shipment_order

    shipment_order.delivery_status = new_status

    if new_status == DeliveryStatus.DELIVERED:
        shipment_order.delivered_at = timezone.now()
        Order.objects.filter(pk=shipment_order.order_id).update(status=OrderStatus.DELIVERED)
        notifications.notify_client_order_delivered(shipment_order.order)
    else:
        shipment_order.delivered_at = None
        if old_status == DeliveryStatus.DELIVERED:
            # Reverting an accidental delivery — put order back to IN_SHIPMENT
            Order.objects.filter(pk=shipment_order.order_id).update(status=OrderStatus.IN_SHIPMENT)
        elif new_status == DeliveryStatus.DISPATCHED:
            notifications.notify_client_order_dispatched(shipment_order.order)

    shipment_order.save(update_fields=['delivery_status', 'delivered_at'])
    _sync_shipment_status(shipment_order.shipment)
    return shipment_order


def _sync_shipment_status(shipment):
    """
    Recompute Shipment.status from its orders' delivery statuses.
    All DELIVERED → DELIVERED; any DISPATCHED → DISPATCHED; all PENDING → PREPARING.
    """
    statuses = list(
        ShipmentOrder.objects.filter(shipment=shipment).values_list('delivery_status', flat=True)
    )
    if not statuses:
        return
    status_set = set(statuses)
    if status_set == {DeliveryStatus.DELIVERED}:
        Shipment.objects.filter(pk=shipment.pk).update(
            status=ShipmentStatus.DELIVERED,
            delivered_at=timezone.now(),
        )
    elif DeliveryStatus.DISPATCHED in status_set:
        Shipment.objects.filter(pk=shipment.pk).update(
            status=ShipmentStatus.DISPATCHED,
            delivered_at=None,
        )
        # Only stamp dispatched_at once
        Shipment.objects.filter(pk=shipment.pk, dispatched_at__isnull=True).update(
            dispatched_at=timezone.now(),
        )
    else:
        Shipment.objects.filter(pk=shipment.pk).update(
            status=ShipmentStatus.PREPARING,
            dispatched_at=None,
            delivered_at=None,
        )


# ── Invites ───────────────────────────────────────────────────────────────


# ── Payments ──────────────────────────────────────────────────────────────


def record_payment(supplier, client, amount, notes, date, order=None, created_by=None):
    if amount <= 0:
        raise ValueError("To'lov miqdori musbat bo'lishi kerak.")
    return PaymentRecord.objects.create(
        supplier=supplier,
        client=client,
        amount=amount,
        notes=notes,
        date=date,
        order=order,
        created_by=created_by,
    )


def update_payment(payment, amount, notes, date, order=None):
    if amount <= 0:
        raise ValueError("To'lov miqdori musbat bo'lishi kerak.")
    payment.amount = amount
    payment.notes = notes
    payment.date = date
    payment.order = order
    payment.save(update_fields=['amount', 'notes', 'date', 'order'])
    return payment


def delete_payment(payment):
    payment.delete()


def _compute_order_effective_total(order):
    """Single aggregate query for effective_retail * quantity across all order items."""
    return order.order_items.aggregate(
        total=Coalesce(
            Sum(
                ExpressionWrapper(
                    Case(
                        When(adjusted_retail_price__isnull=False, then=F('adjusted_retail_price')),
                        default=F('retail_price'),
                        output_field=DecimalField(max_digits=10, decimal_places=2),
                    ) * F('quantity'),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )['total']


@transaction.atomic
def mark_order_paid(order, supplier, actor):
    """
    Deduct order's effective total from client's account balance and mark as PAID.
    Raises ValueError if order is not DELIVERED, already PAID, or balance insufficient.
    """
    if order.status != OrderStatus.DELIVERED:
        raise ValueError("Faqat yetkazilgan buyurtmani to'langan deb belgilash mumkin.")
    if order.payment_status == PaymentStatus.PAID:
        raise ValueError("Bu buyurtma allaqachon to'langan.")

    order_total = _compute_order_effective_total(order)
    balance_data = get_client_balance(supplier, order.client)

    if balance_data['balance'] < order_total:
        shortfall = order_total - balance_data['balance']
        raise ValueError(
            f"Balans yetarli emas. Etishmovchi: {shortfall:,.0f} so'm. "
            f"Avval mijoz balansini to'ldiring."
        )

    order.payment_status = PaymentStatus.PAID
    order.paid_at = timezone.now()
    order.paid_amount = order_total
    order.save(update_fields=['payment_status', 'paid_at', 'paid_amount'])
    return order


@transaction.atomic
def unmark_order_paid(order, actor):
    """Reverse a PAID order back to PENDING, restoring the balance."""
    if order.payment_status != PaymentStatus.PAID:
        raise ValueError("Bu buyurtma to'lanmagan.")
    order.payment_status = PaymentStatus.PENDING
    order.paid_at = None
    order.paid_amount = None
    order.save(update_fields=['payment_status', 'paid_at', 'paid_amount'])
    return order


def get_client_balance(supplier, client):
    """
    Returns {
        'deposited': Decimal,      # total payments received from client
        'settled': Decimal,        # total paid_amount for PAID orders
        'balance': Decimal,        # deposited - settled (available credit)
        'pending_total': Decimal,  # effective total of DELIVERED+PENDING orders (open debt)
    }
    3 queries.
    """
    deposited = PaymentRecord.objects.filter(
        supplier=supplier, client=client,
    ).aggregate(
        total=Coalesce(Sum('amount'), Value(Decimal('0')), output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total']

    settled = Order.objects.filter(
        supplier=supplier, client=client, payment_status=PaymentStatus.PAID,
    ).aggregate(
        total=Coalesce(Sum('paid_amount'), Value(Decimal('0')), output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total']

    _eff_price = Case(
        When(order_items__adjusted_retail_price__isnull=False, then=F('order_items__adjusted_retail_price')),
        default=F('order_items__retail_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    _line = ExpressionWrapper(
        _eff_price * F('order_items__quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    pending_total = Order.objects.filter(
        supplier=supplier, client=client,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.PENDING,
    ).aggregate(
        total=Coalesce(Sum(_line), Value(Decimal('0')), output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total']

    return {
        'deposited': deposited,
        'settled': settled,
        'balance': deposited - settled,
        'pending_total': pending_total,
    }


def get_clients_balance_map(supplier):
    """
    Returns {client_id: {'deposited', 'settled', 'balance', 'pending_count', 'last_order_date'}}
    4 aggregate queries — no N+1.
    """
    deposited = {
        row['client_id']: row['total']
        for row in PaymentRecord.objects.filter(supplier=supplier)
        .values('client_id')
        .annotate(total=Coalesce(
            Sum('amount'), Value(Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ))
    }

    settled = {
        row['client_id']: row['total']
        for row in Order.objects.filter(supplier=supplier, payment_status=PaymentStatus.PAID)
        .values('client_id')
        .annotate(total=Coalesce(
            Sum('paid_amount'), Value(Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ))
    }

    last_order = {
        row['client_id']: row['last']
        for row in Order.objects.filter(supplier=supplier)
        .exclude(status=OrderStatus.DRAFT)
        .values('client_id')
        .annotate(last=Max('submitted_at'))
    }

    pending_counts = {
        row['client_id']: row['cnt']
        for row in Order.objects.filter(
            supplier=supplier, status=OrderStatus.DELIVERED, payment_status=PaymentStatus.PENDING,
        )
        .values('client_id')
        .annotate(cnt=Count('id'))
    }

    zero = Decimal('0')
    all_ids = set(deposited) | set(settled) | set(last_order) | set(pending_counts)
    return {
        cid: {
            'deposited': deposited.get(cid, zero),
            'settled': settled.get(cid, zero),
            'balance': deposited.get(cid, zero) - settled.get(cid, zero),
            'pending_count': pending_counts.get(cid, 0),
            'last_order_date': last_order.get(cid),
        }
        for cid in all_ids
    }


# ── Expenses ──────────────────────────────────────────────────────────────


def create_expense(supplier, amount, notes, date, created_by):
    if amount <= 0:
        raise ValueError("Xarajat miqdori musbat bo'lishi kerak.")
    return Expense.objects.create(
        supplier=supplier,
        amount=amount,
        notes=notes,
        date=date,
        created_by=created_by,
    )


def get_expenses(supplier, date_from=None, date_to=None):
    qs = Expense.objects.filter(supplier=supplier).order_by('-date', '-created_at')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


# ── Invites ───────────────────────────────────────────────────────────────


@transaction.atomic
def register_via_invite(token, company_name, full_name, phone, password):
    """Validate token, create User+Client+SupplierClient, mark invite used."""
    try:
        invite = ClientInvite.objects.select_related('supplier').get(token=token)
    except ClientInvite.DoesNotExist:
        raise ValueError('Taklif havolasi topilmadi.')

    if invite.is_used:
        raise ValueError('Bu havola allaqachon ishlatilgan.')
    if invite.is_expired:
        raise ValueError("Havolaning muddati o'tgan.")

    username = phone.strip()
    if User.objects.filter(username=username).exists():
        username = f'{username}_{uuid.uuid4().hex[:4]}'
    user = User.objects.create_user(
        username=username, password=password, first_name=full_name,
    )
    client = Client.objects.create(user=user, company_name=company_name, phone=phone)
    SupplierClient.objects.create(supplier=invite.supplier, client=client)

    invite.is_used = True
    invite.used_by = client
    invite.save(update_fields=['is_used', 'used_by'])
    return client
