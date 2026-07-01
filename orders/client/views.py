import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View

from orders.constants import OrderStatus
from orders.decorators import ClientLoginRequiredMixin, client_required
from orders.forms import InviteRegisterForm
from orders.models import ClientInvite, Order, SupplierClient
from orders.services import (
    get_client_balance, get_client_catalog, get_client_ledger_page,
    get_client_orders, get_or_create_order_invoice,
    register_via_invite, submit_order as _submit_order,
)

logger = logging.getLogger(__name__)


# ── Auth ───────────────────────────────────────────────────────────────────


class ClientLoginView(LoginView):
    template_name = 'orders/client/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('orders_client:client_catalog')

    def form_valid(self, form):
        user = form.get_user()
        if not hasattr(user, 'client'):
            form.add_error(None, 'Bu foydalanuvchi mijoz emas.')
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_default_redirect_url(self):
        return reverse('orders_client:client_catalog')


def client_logout(request):
    logout(request)
    return redirect(reverse('orders_client:client_login'))


# ── Invite registration ────────────────────────────────────────────────────


def invite_register(request, token):
    try:
        invite = ClientInvite.objects.select_related('supplier').get(token=token)
    except ClientInvite.DoesNotExist:
        return render(request, 'orders/client/invite_invalid.html', {'reason': 'not_found'})

    if invite.is_used:
        return render(request, 'orders/client/invite_invalid.html', {'reason': 'used'})
    if invite.is_expired:
        return render(request, 'orders/client/invite_invalid.html', {'reason': 'expired'})

    if request.method == 'POST':
        form = InviteRegisterForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                client = register_via_invite(
                    token=token,
                    company_name=d['company_name'],
                    full_name=d['full_name'],
                    phone=d['phone'],
                    password=d['password'],
                )
                login(request, client.user)
                return redirect(reverse('orders_client:client_catalog'))
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = InviteRegisterForm()

    return render(request, 'orders/client/register.html', {
        'form': form,
        'invite': invite,
        'supplier': invite.supplier,
    })


# ── Catalog ────────────────────────────────────────────────────────────────


class CatalogView(ClientLoginRequiredMixin, View):
    def get(self, request):
        client = request.user.client
        links = (
            SupplierClient.objects
            .filter(client=client, is_active=True)
            .select_related('supplier')
            .order_by('supplier__business_name')
        )

        if not links.exists():
            return render(request, 'orders/client/no_supplier.html', {'client': client})

        if links.count() == 1:
            supplier = links.first().supplier
        else:
            supplier_id = request.GET.get('supplier')
            if supplier_id:
                try:
                    supplier = links.get(supplier__pk=supplier_id).supplier
                except SupplierClient.DoesNotExist:
                    supplier = links.first().supplier
            else:
                return render(request, 'orders/client/supplier_picker.html', {
                    'client': client,
                    'supplier_links': links,
                })

        categories, uncategorised = get_client_catalog(supplier)
        return render(request, 'orders/client/catalog.html', {
            'client': client,
            'supplier': supplier,
            'supplier_links': links,
            'categories': categories,
            'uncategorised': uncategorised,
        })


# ── Order submission ───────────────────────────────────────────────────────


@client_required
def submit_order(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': "Noto'g'ri so'rov formati."}, status=400)

    supplier_id = body.get('supplier_id')
    raw_items = body.get('items', [])
    notes = str(body.get('notes', '')).strip()

    if not supplier_id:
        return JsonResponse({'error': "Ta'minotchi ko'rsatilmagan."}, status=400)

    if not raw_items:
        return JsonResponse({'error': "Savat bo'sh."}, status=400)

    client = request.user.client

    try:
        sc = SupplierClient.objects.select_related('supplier').get(
            client=client, supplier_id=int(supplier_id), is_active=True
        )
    except (SupplierClient.DoesNotExist, TypeError, ValueError):
        return JsonResponse({'error': "Ta'minotchi topilmadi."}, status=400)

    parsed_items = []
    for ci in raw_items:
        try:
            parsed_items.append({
                'item_id': int(ci['item_id']),
                'quantity': Decimal(str(ci.get('quantity', 1))),
            })
        except (TypeError, ValueError, KeyError, InvalidOperation):
            return JsonResponse({'error': "Noto'g'ri tovar ma'lumotlari."}, status=400)

    try:
        order = _submit_order(
            client=client,
            supplier=sc.supplier,
            cart_items=parsed_items,
            notes=notes,
        )
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({
        'order_id': order.pk,
        'redirect_url': reverse('orders_client:client_order_detail', args=[order.pk]),
    })


# ── Order history ──────────────────────────────────────────────────────────


@client_required
def client_order_list(request):
    client = request.user.client
    tab = request.GET.get('tab', 'active')
    if tab == 'history':
        orders = list(get_client_orders(client, statuses=OrderStatus.CLOSED))
    else:
        tab = 'active'
        orders = list(get_client_orders(client, statuses=OrderStatus.ACTIVE))
    return render(request, 'orders/client/order_list.html', {
        'client': client,
        'orders': orders,
        'active_tab': tab,
    })


@client_required
def client_order_detail(request, pk):
    client = request.user.client
    order = get_object_or_404(
        Order.objects
        .select_related('supplier')
        .prefetch_related('order_items'),
        pk=pk,
        client=client,
    )
    if request.GET.get('partial') == '1':
        return render(request, 'orders/client/_order_detail_content.html', {'order': order})
    return render(request, 'orders/client/order_detail.html', {
        'client': client,
        'order': order,
    })


# ── Invoice — Task 14 ──────────────────────────────────────────────────────


_PAYMENT_PAGE_SIZE = 20


def _resolve_supplier_for_client(client, request):
    """Return (supplier, links_qs). supplier is None only if no active links exist."""
    links = (
        SupplierClient.objects
        .filter(client=client, is_active=True)
        .select_related('supplier')
        .order_by('supplier__business_name')
    )
    if not links.exists():
        return None, links
    if links.count() == 1:
        return links.first().supplier, links
    supplier_id = request.GET.get('supplier')
    if supplier_id:
        try:
            return links.get(supplier__pk=int(supplier_id)).supplier, links
        except (SupplierClient.DoesNotExist, ValueError, TypeError):
            pass
    return links.first().supplier, links


@client_required
def client_payments(request):
    client = request.user.client
    supplier, links = _resolve_supplier_for_client(client, request)

    if supplier is None:
        return render(request, 'orders/client/no_supplier.html', {'client': client})

    try:
        page_num = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page_num = 1

    balance = get_client_balance(supplier, client)
    entries, has_next = get_client_ledger_page(supplier, client, page=page_num, page_size=_PAYMENT_PAGE_SIZE)

    if request.GET.get('partial') == '1':
        return render(request, 'orders/client/_payment_entries.html', {
            'entries': entries,
            'has_next': has_next,
            'next_page': page_num + 1,
            'supplier': supplier,
        })

    return render(request, 'orders/client/payments.html', {
        'client': client,
        'supplier': supplier,
        'supplier_links': links,
        'balance': balance,
        'entries': entries,
        'has_next': has_next,
        'next_page': 2,
    })


_INVOICE_ALLOWED_STATUSES = {
    OrderStatus.ACCEPTED, OrderStatus.IN_SHIPMENT, OrderStatus.DELIVERED,
}


@client_required
def client_invoice_download(request, order_pk):
    client = request.user.client
    order = get_object_or_404(Order, pk=order_pk, client=client)

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
        f'inline; filename="invoice_{invoice.invoice_number}.pdf"'
    )
    return response


# ── Telegram account linking ───────────────────────────────────────────────


@client_required
def link_telegram(request):
    """
    Client visits this URL (with ?token=<short_lived_token>) after clicking the
    bot link.  The token was stored in cache by the /start handler with the
    sender's telegram_id as the value.  We save that telegram_id to the Client
    profile and confirm to the user.
    """
    token = request.GET.get('token', '')
    if not token:
        return render(request, 'orders/client/link_telegram.html', {'error': 'Token kiritilmagan.'})

    telegram_id = cache.get(f'telegram:link:client:{token}')
    if telegram_id is None:
        return render(request, 'orders/client/link_telegram.html', {'error': 'Token muddati o\'tgan yoki yaroqsiz.'})

    client = request.user.client
    from orders.models import Client
    if Client.objects.filter(telegram_id=telegram_id).exclude(pk=client.pk).exists():
        return render(request, 'orders/client/link_telegram.html', {
            'error': 'Bu Telegram akkaunt allaqachon boshqa hisob bilan bog\'langan.',
        })

    client.telegram_id = telegram_id
    client.save(update_fields=['telegram_id'])
    cache.delete(f'telegram:link:client:{token}')

    from orders.celery_tasks import send_telegram_welcome
    send_telegram_welcome.delay(telegram_id, 'client', client.company_name)

    return render(request, 'orders/client/link_telegram.html', {'success': True})
