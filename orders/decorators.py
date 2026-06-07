import functools
import logging

from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)


def _supplier_login_url(next_path=None):
    url = reverse('orders_dashboard:supplier_login')
    if next_path:
        url += f'?next={next_path}'
    return url


def _client_login_url(next_path=None):
    url = reverse('orders_client:client_login')
    if next_path:
        url += f'?next={next_path}'
    return url


def supplier_required(view_func):
    """Decorator for function-based views: requires an authenticated Supplier user."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(_supplier_login_url(request.path))
        if not hasattr(request.user, 'supplier'):
            return redirect(_supplier_login_url())
        return view_func(request, *args, **kwargs)
    return wrapper


def client_required(view_func):
    """Decorator for function-based views: requires an authenticated Client user."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(_client_login_url(request.path))
        if not hasattr(request.user, 'client'):
            return redirect(_client_login_url())
        return view_func(request, *args, **kwargs)
    return wrapper


class ClientLoginRequiredMixin:
    """Mixin for class-based views: requires an authenticated Client user."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(_client_login_url(request.path))
        if not hasattr(request.user, 'client'):
            return redirect(_client_login_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['client'] = self.request.user.client
        return ctx


class SupplierLoginRequiredMixin:
    """Mixin for class-based views: requires an authenticated Supplier user."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(_supplier_login_url(request.path))
        if not hasattr(request.user, 'supplier'):
            return redirect(_supplier_login_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['supplier'] = self.request.user.supplier
        return ctx
