import logging

from django.shortcuts import get_object_or_404, render

from orders.models import LandingCard, Supplier

logger = logging.getLogger(__name__)


def landing_page(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    cards = list(
        LandingCard.objects
        .filter(supplier=supplier, is_active=True)
        .prefetch_related('images')
        .select_related('item')
        .order_by('display_order', 'created_at')
    )
    return render(request, 'orders/landing/landing.html', {
        'supplier': supplier,
        'cards': cards,
    })
