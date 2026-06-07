import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from orders.constants import OrderStatus
from orders.models import Category, Client, ClientInvite, Item, Order, OrderItem, SupplierClient

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
