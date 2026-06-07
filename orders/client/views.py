import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View

from orders.decorators import ClientLoginRequiredMixin, client_required
from orders.forms import InviteRegisterForm
from orders.models import ClientInvite, SupplierClient
from orders.services import get_client_catalog, register_via_invite, submit_order as _submit_order

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
            return render(request, 'orders/client/no_supplier.html')

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
                    'supplier_links': links,
                })

        categories, uncategorised = get_client_catalog(supplier)
        return render(request, 'orders/client/catalog.html', {
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
        'redirect_url': reverse('orders_client:client_catalog'),
    })
