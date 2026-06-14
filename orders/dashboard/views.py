import json
import logging
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView

from orders.constants import DeliveryStatus, OrderStatus, ShipmentStatus
from orders.decorators import SupplierLoginRequiredMixin, supplier_required
from orders.analytics import (
    get_kpis, get_per_client_breakdown, get_revenue_over_time, get_top_clients, get_top_items,
)
from orders.forms import CategoryForm, ClientCreateForm, ClientEditForm, ExpenseForm, ItemForm, PaymentRecordForm
from orders.models import (
    Category, Expense, Item, Order, OrderItem, PaymentRecord, Shipment, ShipmentOrder, SupplierClient,
)
from orders.services import (
    accept_order, add_orders_to_shipment, adjust_order_item_price, archive_item,
    create_client_manually, create_expense, create_shipment_with_orders, decline_order,
    delete_category, delete_payment, generate_invite, get_active_invites, get_client_balance,
    get_clients_balance_map, get_expenses, get_or_create_order_invoice, get_supplier_catalog,
    get_supplier_clients, mark_order_paid, unmark_order_paid, reactivate_item, record_payment,
    update_order_note, update_payment, update_shipment_order_status,
)

logger = logging.getLogger(__name__)


# ── Auth ───────────────────────────────────────────────────────────────────


class SupplierLoginView(LoginView):
    template_name = 'orders/supplier/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('orders_dashboard:dashboard_home')

    def form_valid(self, form):
        user = form.get_user()
        if not hasattr(user, 'supplier'):
            form.add_error(None, "Bu foydalanuvchi ta'minotchi emas.")
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_default_redirect_url(self):
        return reverse('orders_dashboard:dashboard_home')


def supplier_logout(request):
    logout(request)
    return redirect(reverse('orders_dashboard:supplier_login'))


# ── Stub home (used for unimplemented nav links) ───────────────────────────


class DashboardHomeView(SupplierLoginRequiredMixin, TemplateView):
    template_name = 'orders/supplier/home.html'


# ── Order queue ────────────────────────────────────────────────────────────

_VALID_STATUS_FILTERS = {
    OrderStatus.SUBMITTED, OrderStatus.ACCEPTED,
    OrderStatus.DECLINED, OrderStatus.IN_SHIPMENT, OrderStatus.DELIVERED,
}

# Effective unit price per order item: adjusted if set, else original snapshot.
_EFFECTIVE_UNIT_PRICE = Case(
    When(
        order_items__adjusted_retail_price__isnull=False,
        then=F('order_items__adjusted_retail_price'),
    ),
    default=F('order_items__retail_price'),
    output_field=DecimalField(max_digits=10, decimal_places=2),
)

_LINE_TOTAL = ExpressionWrapper(
    _EFFECTIVE_UNIT_PRICE * F('order_items__quantity'),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


@supplier_required
def order_queue(request):
    supplier = request.user.supplier
    status_filter = request.GET.get('status', '')

    qs = (
        Order.objects
        .filter(supplier=supplier)
        .exclude(status=OrderStatus.DRAFT)
        .select_related('client')
        .annotate(
            item_count=Count('order_items', distinct=True),
            order_total=Coalesce(
                Sum(_LINE_TOTAL),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-submitted_at')
    )

    if status_filter in _VALID_STATUS_FILTERS:
        qs = qs.filter(status=status_filter)

    return render(request, 'orders/supplier/order_queue.html', {
        'orders': qs,
        'status_filter': status_filter,
        'OrderStatus': OrderStatus,
    })


@supplier_required
def order_detail(request, pk):
    supplier = request.user.supplier
    order = get_object_or_404(
        Order.objects
        .select_related('client')
        .prefetch_related('order_items__item'),
        pk=pk,
        supplier=supplier,
    )
    client_balance = None
    if order.status == OrderStatus.DELIVERED:
        client_balance = get_client_balance(supplier, order.client)
    return render(request, 'orders/supplier/order_detail.html', {
        'order': order,
        'client_balance': client_balance,
        'nav_section': 'dashboard_home',
    })


@supplier_required
def order_mark_paid(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    order = get_object_or_404(Order.objects.select_related('client'), pk=pk, supplier=supplier)
    try:
        mark_order_paid(order, supplier, request.user)
        messages.success(request, f"Buyurtma #{pk} to'langan deb belgilandi.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(reverse('orders_dashboard:order_detail', args=[pk]))


@supplier_required
def order_unmark_paid(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    order = get_object_or_404(Order, pk=pk, supplier=supplier)
    try:
        unmark_order_paid(order, request.user)
        messages.success(request, f"Buyurtma #{pk} to'lov holati qaytarildi.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(reverse('orders_dashboard:order_detail', args=[pk]))


@supplier_required
def order_accept(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    order = get_object_or_404(Order, pk=pk, supplier=supplier)
    try:
        accept_order(order, request.user)
        messages.success(request, f'Buyurtma #{pk} qabul qilindi.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(reverse('orders_dashboard:order_detail', args=[pk]))


@supplier_required
def order_decline(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    order = get_object_or_404(Order, pk=pk, supplier=supplier)
    note = request.POST.get('note', '').strip()
    try:
        decline_order(order, request.user, note=note)
        messages.success(request, f'Buyurtma #{pk} rad etildi.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(reverse('orders_dashboard:order_detail', args=[pk]))


@supplier_required
def order_adjust_price(request, order_pk, item_pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    supplier = request.user.supplier
    order = get_object_or_404(Order, pk=order_pk, supplier=supplier)

    try:
        order_item = OrderItem.objects.get(pk=item_pk, order_id=order.pk)
    except OrderItem.DoesNotExist:
        return JsonResponse({'error': 'Tovar topilmadi.'}, status=404)

    order_item.order = order  # attach loaded order to avoid an extra DB hit in service

    try:
        body = json.loads(request.body)
        new_price = Decimal(str(body.get('new_price', '')))
    except (json.JSONDecodeError, ValueError, InvalidOperation):
        return JsonResponse({'error': "Noto'g'ri narx formati."}, status=400)

    try:
        order_item = adjust_order_item_price(order_item, new_price, request.user)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    line_total = order_item.effective_retail * order_item.quantity
    return JsonResponse({
        'ok': True,
        'effective_retail': int(round(float(order_item.effective_retail))),
        'line_total': int(round(float(line_total))),
    })


@supplier_required
def order_update_note(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    supplier = request.user.supplier
    order = get_object_or_404(Order, pk=pk, supplier=supplier)
    try:
        body = json.loads(request.body)
        note = str(body.get('note', ''))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': "Noto'g'ri so'rov formati."}, status=400)
    update_order_note(order, note)
    return JsonResponse({'ok': True})


# ── Catalog ────────────────────────────────────────────────────────────────


@supplier_required
def catalog_management(request):
    supplier = request.user.supplier
    categories, uncategorised = get_supplier_catalog(supplier)
    return render(request, 'orders/supplier/catalog.html', {
        'categories': categories,
        'uncategorised': uncategorised,
    })


@supplier_required
def category_create(request):
    supplier = request.user.supplier
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.supplier = supplier
            category.save()
            messages.success(request, f'"{category.name}" kategoriyasi qo\'shildi.')
            return redirect(reverse('orders_dashboard:catalog_home'))
    else:
        form = CategoryForm()
    return render(request, 'orders/supplier/category_form.html', {'form': form, 'is_new': True})


@supplier_required
def category_update(request, pk):
    supplier = request.user.supplier
    category = get_object_or_404(Category, pk=pk, supplier=supplier)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{category.name}" yangilandi.')
            return redirect(reverse('orders_dashboard:catalog_home'))
    else:
        form = CategoryForm(instance=category)
    return render(request, 'orders/supplier/category_form.html', {
        'form': form,
        'is_new': False,
        'category': category,
    })


@supplier_required
def category_delete(request, pk):
    supplier = request.user.supplier
    category = get_object_or_404(Category, pk=pk, supplier=supplier)
    if request.method == 'POST':
        name = category.name
        delete_category(category)
        messages.success(request, f'"{name}" kategoriyasi o\'chirildi. Tovarlar saqlanib qoldi.')
    return redirect(reverse('orders_dashboard:catalog_home'))


@supplier_required
def item_create(request):
    supplier = request.user.supplier
    if request.method == 'POST':
        form = ItemForm(supplier, request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.supplier = supplier
            item.save()
            messages.success(request, f'"{item.name}" tovar qo\'shildi.')
            return redirect(reverse('orders_dashboard:catalog_home'))
    else:
        form = ItemForm(supplier)
    return render(request, 'orders/supplier/item_form.html', {'form': form, 'is_new': True})


@supplier_required
def item_update(request, pk):
    supplier = request.user.supplier
    item = get_object_or_404(Item, pk=pk, supplier=supplier)
    if request.method == 'POST':
        form = ItemForm(supplier, request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{item.name}" yangilandi.')
            return redirect(reverse('orders_dashboard:catalog_home'))
    else:
        form = ItemForm(supplier, instance=item)
    return render(request, 'orders/supplier/item_form.html', {
        'form': form,
        'is_new': False,
        'item': item,
    })


@supplier_required
def item_archive(request, pk):
    supplier = request.user.supplier
    item = get_object_or_404(Item, pk=pk, supplier=supplier)
    if request.method == 'POST':
        archive_item(item)
        messages.success(request, f'"{item.name}" arxivlandi.')
    return redirect(reverse('orders_dashboard:catalog_home'))


@supplier_required
def item_reactivate(request, pk):
    supplier = request.user.supplier
    item = get_object_or_404(Item, pk=pk, supplier=supplier)
    if request.method == 'POST':
        reactivate_item(item)
        messages.success(request, f'"{item.name}" faollashtirildi.')
    return redirect(reverse('orders_dashboard:catalog_home'))


# ── Client management ──────────────────────────────────────────────────────


_ZERO = Decimal('0')
_DEFAULT_BALANCE = {
    'deposited': _ZERO, 'settled': _ZERO, 'balance': _ZERO,
    'pending_count': 0, 'last_order_date': None,
}


@supplier_required
def client_list(request):
    supplier = request.user.supplier
    supplier_clients = list(get_supplier_clients(supplier))
    balance_map = get_clients_balance_map(supplier)
    for sc in supplier_clients:
        sc.balance = balance_map.get(sc.client_id, _DEFAULT_BALANCE)
    active_invites = get_active_invites(supplier)
    return render(request, 'orders/supplier/clients.html', {
        'supplier_clients': supplier_clients,
        'active_invites': active_invites,
    })


@supplier_required
def client_detail(request, pk):
    supplier = request.user.supplier
    sc = get_object_or_404(
        SupplierClient.objects.select_related('client', 'client__user'),
        client_id=pk, supplier=supplier,
    )
    client = sc.client

    if request.method == 'POST':
        payment_form = PaymentRecordForm(supplier, client, request.POST)
        if payment_form.is_valid():
            d = payment_form.cleaned_data
            try:
                record_payment(
                    supplier=supplier,
                    client=client,
                    amount=d['amount'],
                    notes=d.get('notes', ''),
                    date=d['date'],
                    order=d.get('order'),
                    created_by=request.user,
                )
                messages.success(request, f"To'lov {d['amount']:,.0f} so'm qo'shildi.")
                return redirect(reverse('orders_dashboard:client_detail', args=[pk]))
            except ValueError as e:
                payment_form.add_error(None, str(e))
    else:
        payment_form = PaymentRecordForm(supplier, client, initial={'date': timezone.localdate()})

    balance = get_client_balance(supplier, client)

    orders = (
        Order.objects
        .filter(supplier=supplier, client=client)
        .exclude(status=OrderStatus.DRAFT)
        .annotate(
            item_count=Count('order_items', distinct=True),
            order_total=Coalesce(
                Sum(_LINE_TOTAL),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-submitted_at')
    )

    payments_list = list(
        PaymentRecord.objects
        .filter(supplier=supplier, client=client)
        .select_related('order')
        .order_by('-date', '-created_at')
    )
    payments_data = [
        {
            'id': p.pk,
            'amount': p.amount,
            'date': p.date,
            'orderId': p.order_id or '',
            'notes': p.notes,
            'updateUrl': reverse('orders_dashboard:payment_update', args=[client.pk, p.pk]),
            'deleteUrl': reverse('orders_dashboard:payment_delete', args=[client.pk, p.pk]),
        }
        for p in payments_list
    ]

    return render(request, 'orders/supplier/client_detail.html', {
        'sc': sc,
        'client': client,
        'balance': balance,
        'orders': orders,
        'payments': payments_list,
        'payments_data': payments_data,
        'payment_form': payment_form,
        'OrderStatus': OrderStatus,
        'nav_section': 'client_list',
    })


@supplier_required
def client_update(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    sc = get_object_or_404(SupplierClient, client_id=pk, supplier=supplier)
    client = sc.client
    form = ClientEditForm(request.POST, client_pk=client.pk)
    if form.is_valid():
        d = form.cleaned_data
        client.company_name = d['company_name']
        client.phone = d['phone']
        client.address = d.get('address', '')
        new_lat = d.get('latitude')
        new_lng = d.get('longitude')
        location_changed = (new_lat != client.latitude) or (new_lng != client.longitude)
        client.latitude = new_lat
        client.longitude = new_lng
        if location_changed:
            client.location_updated_at = timezone.now()
        client.telegram_id = d.get('telegram_id') or None
        client.save(update_fields=[
            'company_name', 'phone', 'address',
            'latitude', 'longitude', 'location_updated_at',
            'telegram_id',
        ])
        email = d.get('email', '') or ''
        if client.user.email != email:
            client.user.email = email
            client.user.save(update_fields=['email'])
        return JsonResponse({'ok': True})
    errors = {field: list(errs) for field, errs in form.errors.items()}
    return JsonResponse({'ok': False, 'errors': errors}, status=400)


@supplier_required
def order_detail_partial(request, pk):
    supplier = request.user.supplier
    order = get_object_or_404(
        Order.objects
        .select_related('client')
        .prefetch_related('order_items__item'),
        pk=pk,
        supplier=supplier,
    )
    return render(request, 'orders/supplier/_order_detail_modal.html', {'order': order})


@supplier_required
def payment_update(request, client_pk, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    sc = get_object_or_404(SupplierClient, client_id=client_pk, supplier=supplier)
    payment = get_object_or_404(PaymentRecord, pk=pk, supplier=supplier, client_id=client_pk)
    form = PaymentRecordForm(supplier, sc.client, request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            update_payment(
                payment,
                amount=d['amount'],
                notes=d.get('notes', ''),
                date=d['date'],
                order=d.get('order'),
            )
            return JsonResponse({'ok': True})
        except ValueError as e:
            return JsonResponse({'ok': False, 'errors': {'__all__': [str(e)]}}, status=400)
    errors = {field: list(errs) for field, errs in form.errors.items()}
    return JsonResponse({'ok': False, 'errors': errors}, status=400)


@supplier_required
def payment_delete(request, client_pk, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    get_object_or_404(SupplierClient, client_id=client_pk, supplier=supplier)
    payment = get_object_or_404(PaymentRecord, pk=pk, supplier=supplier, client_id=client_pk)
    delete_payment(payment)
    return JsonResponse({'ok': True})


@supplier_required
def client_create(request):
    supplier = request.user.supplier
    if request.method == 'POST':
        form = ClientCreateForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                client = create_client_manually(
                    supplier=supplier,
                    company_name=d['company_name'],
                    phone=d['phone'],
                    full_name=d['full_name'],
                    password=d['password'],
                    email=d.get('email', ''),
                )
                messages.success(request, f'"{client.company_name}" mijozi qo\'shildi.')
                return redirect(reverse('orders_dashboard:client_list'))
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = ClientCreateForm()
    return render(request, 'orders/supplier/client_create.html', {'form': form})


@supplier_required
def invite_generate(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    invite = generate_invite(supplier)
    invite_url = request.build_absolute_uri(
        reverse('orders_client:invite_register', args=[str(invite.token)])
    )
    return JsonResponse({'url': invite_url, 'token': str(invite.token)})


# ── Shipments ──────────────────────────────────────────────────────────────


@supplier_required
def shipment_list(request):
    supplier = request.user.supplier
    status_filter = request.GET.get('status', '')
    valid_statuses = {'PREPARING', 'DISPATCHED', 'DELIVERED'}

    qs = (
        Shipment.objects
        .filter(supplier=supplier)
        .prefetch_related('shipment_orders__order__client')
        .order_by('-created_at')
    )
    if status_filter in valid_statuses:
        qs = qs.filter(status=status_filter)
    else:
        # Default: active only (not delivered); delivered tab loads them explicitly
        qs = qs.exclude(status=ShipmentStatus.DELIVERED)

    shipments = list(qs)
    for shipment in shipments:
        seen = {}
        for so in shipment.shipment_orders.all():
            c = so.order.client
            if c.pk not in seen:
                seen[c.pk] = c
        shipment.unique_clients = list(seen.values())

    return render(request, 'orders/supplier/shipment_list.html', {
        'shipments': shipments,
        'status_filter': status_filter,
        'nav_section': 'shipment_list',
    })


@supplier_required
def shipment_create(request):
    supplier = request.user.supplier
    in_active_shipment_ids = (
        ShipmentOrder.objects
        .exclude(delivery_status=DeliveryStatus.DELIVERED)
        .values_list('order_id', flat=True)
    )
    available_orders = (
        Order.objects
        .filter(supplier=supplier, status=OrderStatus.ACCEPTED)
        .exclude(pk__in=in_active_shipment_ids)
        .select_related('client')
        .order_by('-submitted_at')
    )
    if request.method == 'POST':
        order_ids = request.POST.getlist('order_ids')
        if not order_ids:
            messages.error(request, 'Kamida bitta buyurtma tanlang.')
        else:
            scheduled_date = request.POST.get('scheduled_date') or None
            notes = request.POST.get('notes', '').strip()
            try:
                order_ids = [int(oid) for oid in order_ids]
                shipment = create_shipment_with_orders(
                    supplier, order_ids,
                    scheduled_date=scheduled_date, notes=notes,
                )
                messages.success(request, f"Jo'natma #{shipment.pk} yaratildi.")
                return redirect(reverse('orders_dashboard:shipment_detail', args=[shipment.pk]))
            except (ValueError, TypeError) as e:
                messages.error(request, str(e))
    return render(request, 'orders/supplier/shipment_create.html', {
        'available_orders': available_orders,
        'nav_section': 'shipment_list',
    })


@supplier_required
def shipment_detail(request, pk):
    supplier = request.user.supplier
    shipment = get_object_or_404(
        Shipment.objects
        .prefetch_related(
            'shipment_orders__order__client',
            'shipment_orders__order__order_items',
        ),
        pk=pk,
        supplier=supplier,
    )
    # Assign UI only makes sense while still preparing
    available_orders = []
    if shipment.status == ShipmentStatus.PREPARING:
        in_other_shipment_ids = (
            ShipmentOrder.objects
            .exclude(delivery_status=DeliveryStatus.DELIVERED)
            .exclude(shipment=shipment)
            .values_list('order_id', flat=True)
        )
        available_orders = list(
            Order.objects
            .filter(supplier=supplier, status=OrderStatus.ACCEPTED)
            .exclude(pk__in=in_other_shipment_ids)
            .select_related('client')
            .order_by('-submitted_at')
        )
    shipment_orders = list(shipment.shipment_orders.all())
    all_delivered = bool(shipment_orders) and all(
        so.delivery_status == DeliveryStatus.DELIVERED for so in shipment_orders
    )
    return render(request, 'orders/supplier/shipment_detail.html', {
        'shipment': shipment,
        'shipment_orders': shipment_orders,
        'available_orders': available_orders,
        'all_delivered': all_delivered,
        'DeliveryStatus': DeliveryStatus,
        'ShipmentStatus': ShipmentStatus,
        'nav_section': 'shipment_list',
    })


@supplier_required
def shipment_assign_orders(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    shipment = get_object_or_404(Shipment, pk=pk, supplier=supplier)
    order_ids = request.POST.getlist('order_ids')
    if not order_ids:
        messages.error(request, 'Kamida bitta buyurtma tanlang.')
        return redirect(reverse('orders_dashboard:shipment_detail', args=[pk]))
    try:
        order_ids = [int(oid) for oid in order_ids]
        add_orders_to_shipment(shipment, order_ids)
        messages.success(request, f"{len(order_ids)} ta buyurtma jo'natmaga qo'shildi.")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    return redirect(reverse('orders_dashboard:shipment_detail', args=[pk]))


@supplier_required
def shipment_order_update_status(request, shipment_pk, so_pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    shipment = get_object_or_404(Shipment, pk=shipment_pk, supplier=supplier)
    so = get_object_or_404(ShipmentOrder, pk=so_pk, shipment=shipment)
    new_status = request.POST.get('status', '')
    try:
        update_shipment_order_status(so, new_status, request.user)
        messages.success(request, f'Buyurtma #{so.order_id} holati yangilandi.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(reverse('orders_dashboard:shipment_detail', args=[shipment_pk]))


# ── Expenses — Task 12 ─────────────────────────────────────────────────────


@supplier_required
def expense_list(request):
    supplier = request.user.supplier
    today = timezone.localdate()
    month_start = today.replace(day=1)

    date_from_str = request.GET.get('from', '')
    date_to_str = request.GET.get('to', '')
    is_filtered = bool(date_from_str or date_to_str)

    date_from = month_start
    date_to = today
    filter_errors = []

    if date_from_str:
        try:
            date_from = date_cls.fromisoformat(date_from_str)
        except ValueError:
            filter_errors.append("Noto'g'ri 'dan' sana formati.")
            date_from = month_start
    if date_to_str:
        try:
            date_to = date_cls.fromisoformat(date_to_str)
        except ValueError:
            filter_errors.append("Noto'g'ri 'gacha' sana formati.")
            date_to = today

    expenses = list(get_expenses(supplier, date_from=date_from, date_to=date_to))
    period_total = sum(e.amount for e in expenses)

    form = ExpenseForm(initial={'date': today})

    return render(request, 'orders/supplier/expenses.html', {
        'expenses': expenses,
        'period_total': period_total,
        'form': form,
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'is_filtered': is_filtered,
        'filter_errors': filter_errors,
        'nav_section': 'expense_list',
    })


@supplier_required
def expense_create(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    form = ExpenseForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            create_expense(
                supplier=supplier,
                amount=d['amount'],
                notes=d['notes'],
                date=d['date'],
                created_by=request.user,
            )
            messages.success(request, f"Xarajat {d['amount']:,.0f} so'm qo'shildi.")
        except ValueError as e:
            messages.error(request, str(e))
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
    return redirect(reverse('orders_dashboard:expense_list'))


@supplier_required
def expense_delete(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    supplier = request.user.supplier
    expense = get_object_or_404(Expense, pk=pk, supplier=supplier)
    expense.delete()
    messages.success(request, 'Xarajat o\'chirildi.')
    return redirect(reverse('orders_dashboard:expense_list'))


# ── Analytics — Task 13 ────────────────────────────────────────────────────


def _parse_analytics_dates(request):
    """Return (date_from, date_to) from GET params, defaulting to current month."""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    date_from = month_start
    date_to = today
    if raw := request.GET.get('from', ''):
        try:
            date_from = date_cls.fromisoformat(raw)
        except ValueError:
            pass
    if raw := request.GET.get('to', ''):
        try:
            date_to = date_cls.fromisoformat(raw)
        except ValueError:
            pass
    return date_from, date_to


_BREAKDOWN_COLS = [
    ('company_name', 'Mijoz', ''),
    ('order_count', 'Buyurtmalar', "Tanlangan davrda yetkazilgan buyurtmalar soni"),
    ('revenue', 'Savdo', "Yetkazilgan buyurtmalar bo'yicha umumiy savdo summasi"),
    ('gross_profit', 'Foyda', "Yalpi foyda: savdo summasi minus mahsulot xarid narxi"),
    ('total_paid', "To'lovlar", "Tanlangan davrda ushbu mijozdan qabul qilingan to'lovlar summasi"),
    ('outstanding', 'Qoldiq', "Savdo minus to'lovlar. Musbat — mijoz qarzi, manfiy — ortiqcha to'lov"),
]


@supplier_required
def analytics_dashboard(request):
    date_from, date_to = _parse_analytics_dates(request)
    return render(request, 'orders/supplier/analytics.html', {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'breakdown_cols': _BREAKDOWN_COLS,
        'nav_section': 'analytics',
    })


@supplier_required
def analytics_chart_data(request):
    supplier = request.user.supplier
    date_from, date_to = _parse_analytics_dates(request)
    kpis = get_kpis(supplier, date_from, date_to)
    return JsonResponse({
        'kpis': {k: float(v) if isinstance(v, Decimal) else v for k, v in kpis.items()},
        'revenue_over_time': get_revenue_over_time(supplier, date_from, date_to),
        'top_items': get_top_items(supplier, date_from, date_to),
        'top_clients': get_top_clients(supplier, date_from, date_to),
        'breakdown': get_per_client_breakdown(supplier, date_from, date_to),
    })


# ── Invoice — Task 14 ──────────────────────────────────────────────────────


_INVOICE_ALLOWED_STATUSES = {
    OrderStatus.ACCEPTED, OrderStatus.IN_SHIPMENT, OrderStatus.DELIVERED,
}


@supplier_required
def invoice_download(request, order_pk):
    supplier = request.user.supplier
    order = get_object_or_404(Order, pk=order_pk, supplier=supplier)

    if order.status not in _INVOICE_ALLOWED_STATUSES:
        raise Http404

    try:
        invoice = get_or_create_order_invoice(order, generated_by=request.user)
    except Exception:
        logger.exception('Invoice generation failed for order %s', order_pk)
        return JsonResponse({'error': "Hisob-faktura yaratishda xato yuz berdi."}, status=500)

    response = FileResponse(
        invoice.pdf_file.open('rb'),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    )
    return response
