from django.contrib import admin
from django.utils.html import format_html

from orders.models import (
    Supplier,
    Client,
    SupplierClient,
    ClientInvite,
    Category,
    Item,
    Order,
    OrderItem,
    Shipment,
    ShipmentOrder,
    PaymentRecord,
    Expense,
    Invoice,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'phone', 'telegram_linked', 'created_at']
    search_fields = ['business_name', 'phone', 'user__username', 'user__email']
    readonly_fields = ['created_at']

    @admin.display(boolean=True, description='Telegram')
    def telegram_linked(self, obj):
        return obj.telegram_id is not None


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'phone', 'has_location', 'telegram_linked', 'created_at']
    search_fields = ['company_name', 'phone', 'user__username']
    readonly_fields = ['created_at', 'location_updated_at']

    @admin.display(boolean=True, description='Manzil')
    def has_location(self, obj):
        return obj.has_location

    @admin.display(boolean=True, description='Telegram')
    def telegram_linked(self, obj):
        return obj.telegram_id is not None


@admin.register(SupplierClient)
class SupplierClientAdmin(admin.ModelAdmin):
    list_display = ['client', 'supplier', 'is_active', 'joined_at']
    list_filter = ['is_active', 'supplier']
    search_fields = ['client__company_name', 'supplier__business_name']
    readonly_fields = ['joined_at']


@admin.register(ClientInvite)
class ClientInviteAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'token', 'is_used', 'is_expired', 'expires_at', 'created_at']
    list_filter = ['is_used', 'supplier']
    readonly_fields = ['token', 'created_at']

    @admin.display(boolean=True, description='Muddati o\'tgan')
    def is_expired(self, obj):
        return obj.is_expired


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'supplier', 'display_order']
    list_filter = ['supplier']
    search_fields = ['name', 'supplier__business_name']
    ordering = ['supplier', 'display_order', 'name']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['effective_retail_display', 'line_total_display']
    fields = [
        'item', 'item_name', 'item_unit', 'quantity',
        'retail_price', 'adjusted_retail_price',
        'base_price_snapshot', 'profit_snapshot',
        'effective_retail_display', 'line_total_display',
    ]

    @admin.display(description='Sotuv narxi (amaliy)')
    def effective_retail_display(self, obj):
        return obj.effective_retail

    @admin.display(description='Jami')
    def line_total_display(self, obj):
        return obj.line_total


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'supplier', 'category', 'unit',
        'base_price', 'profit', 'retail_price_display', 'is_active',
    ]
    list_filter = ['is_active', 'supplier', 'unit', 'category']
    search_fields = ['name', 'supplier__business_name']
    readonly_fields = ['retail_price_display', 'created_at', 'updated_at']

    @admin.display(description='Sotuv narxi')
    def retail_price_display(self, obj):
        return obj.retail_price


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'supplier', 'status', 'prices_adjusted', 'submitted_at', 'total_display']
    list_filter = ['status', 'supplier', 'prices_adjusted']
    search_fields = ['client__company_name', 'supplier__business_name']
    readonly_fields = ['created_at', 'updated_at', 'submitted_at', 'accepted_at']
    inlines = [OrderItemInline]

    @admin.display(description='Jami')
    def total_display(self, obj):
        return obj.total


class ShipmentOrderInline(admin.TabularInline):
    model = ShipmentOrder
    extra = 0
    readonly_fields = ['delivered_at']
    fields = ['order', 'delivery_status', 'delivered_at']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'supplier', 'status', 'scheduled_date', 'created_at']
    list_filter = ['status', 'supplier']
    readonly_fields = ['created_at', 'dispatched_at', 'delivered_at']
    inlines = [ShipmentOrderInline]


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ['client', 'supplier', 'amount', 'type', 'date', 'order']
    list_filter = ['type', 'supplier', 'date']
    search_fields = ['client__company_name', 'supplier__business_name', 'notes']
    readonly_fields = ['created_at', 'created_by']
    date_hierarchy = 'date'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'amount', 'notes_short', 'date', 'created_by']
    list_filter = ['supplier', 'date']
    search_fields = ['notes', 'supplier__business_name']
    readonly_fields = ['created_at', 'created_by']
    date_hierarchy = 'date'

    @admin.display(description='Izoh')
    def notes_short(self, obj):
        return obj.notes[:60] + ('…' if len(obj.notes) > 60 else '')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'order', 'type', 'pdf_link', 'generated_at', 'generated_by']
    list_filter = ['type']
    search_fields = ['invoice_number', 'order__id']
    readonly_fields = ['invoice_number', 'generated_at']

    @admin.display(description='PDF')
    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Yuklab olish</a>', obj.pdf_file.url)
        return '—'
