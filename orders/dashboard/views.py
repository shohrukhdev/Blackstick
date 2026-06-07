import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView

from orders.constants import OrderStatus
from orders.decorators import SupplierLoginRequiredMixin, supplier_required
from orders.forms import CategoryForm, ClientCreateForm, ItemForm
from orders.models import Category, Item, Order, OrderItem
from orders.services import (
    accept_order, adjust_order_item_price, archive_item, create_client_manually,
    decline_order, delete_category, generate_invite, get_active_invites,
    get_supplier_catalog, get_supplier_clients, reactivate_item, update_order_note,
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
    return render(request, 'orders/supplier/order_detail.html', {
        'order': order,
        'nav_section': 'dashboard_home',
    })


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


@supplier_required
def client_list(request):
    supplier = request.user.supplier
    supplier_clients = get_supplier_clients(supplier)
    active_invites = get_active_invites(supplier)
    return render(request, 'orders/supplier/clients.html', {
        'supplier_clients': supplier_clients,
        'active_invites': active_invites,
    })


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
