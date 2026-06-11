import uuid
import logging

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from orders.constants import (
    UNIT_CHOICES,
    OrderStatus,
    ShipmentStatus,
    DeliveryStatus,
    PaymentStatus,
    InvoiceType,
)

logger = logging.getLogger(__name__)


class Supplier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='supplier')
    business_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    address = models.TextField(blank=True, default='')
    logo = models.ImageField(upload_to='supplier/logos/', blank=True, null=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"

    def __str__(self):
        return self.business_name


class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client')
    company_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    address = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mijoz'
        verbose_name_plural = 'Mijozlar'

    def __str__(self):
        return self.company_name

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def maps_url(self):
        if self.has_location:
            return f'https://maps.google.com/?q={self.latitude},{self.longitude}'
        return None


class SupplierClient(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='client_links')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='supplier_links')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default='')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('supplier', 'client')
        verbose_name = 'Mijoz-Ta\'minotchi'
        verbose_name_plural = 'Mijoz-Ta\'minotchilar'

    def __str__(self):
        return f'{self.client} ← {self.supplier}'


class ClientInvite(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='invites')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_used = models.BooleanField(default=False)
    used_by = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='invite_used'
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Taklif havolasi'
        verbose_name_plural = 'Taklif havola'
        ordering = ['-created_at']

    def __str__(self):
        return f'Taklif ({self.supplier}) — {"ishlatilgan" if self.is_used else "aktiv"}'

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired


class Category(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=255)
    display_order = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Kategoriya'
        verbose_name_plural = 'Kategoriyalar'
        ordering = ['display_order', 'name']

    def __str__(self):
        return f'{self.name} ({self.supplier})'


class Item(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='items'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image = models.ImageField(upload_to='items/images/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tovar'
        verbose_name_plural = 'Tovarlar'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.supplier})'

    @property
    def retail_price(self):
        return self.base_price + self.profit

    def get_unit_display_uz(self):
        from orders.constants import UNIT_LABELS
        return UNIT_LABELS.get(self.unit, self.unit)


class Order(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='orders')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(
        max_length=20, choices=OrderStatus.CHOICES, default=OrderStatus.DRAFT, db_index=True
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.CHOICES, default=PaymentStatus.PENDING, db_index=True
    )
    notes = models.TextField(blank=True, default='')
    supplier_note = models.TextField(blank=True, default='')
    prices_adjusted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Buyurtma'
        verbose_name_plural = 'Buyurtmalar'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} {self.client} → {self.supplier} [{self.status}]'

    @property
    def total(self):
        return sum(item.line_total for item in self.order_items.all())

    @property
    def is_active(self):
        return self.status in OrderStatus.ACTIVE

    @property
    def is_closed(self):
        return self.status in OrderStatus.CLOSED


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    item_name = models.CharField(max_length=255)
    item_unit = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    retail_price = models.DecimalField(max_digits=10, decimal_places=2)
    adjusted_retail_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    profit_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Buyurtma elementi'
        verbose_name_plural = 'Buyurtma elementlari'

    def __str__(self):
        return f'{self.item_name} × {self.quantity} (Order #{self.order_id})'

    @property
    def effective_retail(self):
        return self.adjusted_retail_price if self.adjusted_retail_price is not None else self.retail_price

    @property
    def effective_profit(self):
        return self.effective_retail - self.base_price_snapshot

    @property
    def line_total(self):
        return self.effective_retail * self.quantity

    @property
    def original_line_total(self):
        return self.retail_price * self.quantity

    @property
    def is_price_adjusted(self):
        return self.adjusted_retail_price is not None


class Shipment(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='shipments')
    status = models.CharField(
        max_length=20, choices=ShipmentStatus.CHOICES, default=ShipmentStatus.PREPARING
    )
    notes = models.TextField(blank=True, default='')
    scheduled_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Jo'natma"
        verbose_name_plural = "Jo'natmalar"
        ordering = ['-created_at']

    def __str__(self):
        date = self.scheduled_date or self.created_at.date()
        return f"Jo'natma #{self.pk} ({self.supplier}) — {date}"


class ShipmentOrder(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='shipment_orders')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='shipment_assignments')
    delivery_status = models.CharField(
        max_length=20, choices=DeliveryStatus.CHOICES, default=DeliveryStatus.PENDING, db_index=True
    )
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('shipment', 'order')
        verbose_name = "Jo'natma buyurtmasi"
        verbose_name_plural = "Jo'natma buyurtmalari"

    def __str__(self):
        return f'Order #{self.order_id} in Shipment #{self.shipment_id} [{self.delivery_status}]'


class PaymentRecord(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payment_records')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payment_records')
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_records'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, default='')
    date = models.DateField(db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payment_records_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"To'lov {self.amount} — {self.client} ({self.date})"


class Expense(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField()
    date = models.DateField(db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='expenses_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Xarajat'
        verbose_name_plural = 'Xarajatlar'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.amount} so\'m — {self.notes[:50]} ({self.date})'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='invoice', null=True, blank=True
    )
    type = models.CharField(max_length=20, choices=InvoiceType.CHOICES, default=InvoiceType.ORDER)
    pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='invoices_generated')

    class Meta:
        verbose_name = 'Hisob-faktura'
        verbose_name_plural = 'Hisob-fakturalar'
        ordering = ['-generated_at']

    def __str__(self):
        return self.invoice_number

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_number()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_number(cls):
        now = timezone.now()
        prefix = f'INV-{now.strftime("%Y%m")}'
        count = cls.objects.filter(invoice_number__startswith=prefix).count()
        return f'{prefix}-{count + 1:04d}'
