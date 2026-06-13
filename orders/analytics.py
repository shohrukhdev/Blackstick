import logging
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek
from django.utils import timezone as django_tz

from orders.constants import DeliveryStatus, OrderStatus
from orders.models import Expense, Order, OrderItem, PaymentRecord

logger = logging.getLogger(__name__)

_ZERO = Decimal('0')
_DF = DecimalField(max_digits=14, decimal_places=2)

# Expressions are relative to OrderItem fields.
_EFF_PRICE = Case(
    When(adjusted_retail_price__isnull=False, then=F('adjusted_retail_price')),
    default=F('retail_price'),
    output_field=DecimalField(max_digits=10, decimal_places=2),
)

_LINE_REVENUE = ExpressionWrapper(
    _EFF_PRICE * F('quantity'),
    output_field=_DF,
)

_LINE_PROFIT = ExpressionWrapper(
    (_EFF_PRICE - F('base_price_snapshot')) * F('quantity'),
    output_field=_DF,
)

# Delivery date path through ShipmentOrder (used in date filter + time-series trunc).
_DELIVERED_AT = 'order__shipment_assignments__delivered_at'


def _delivered_items(supplier, date_from, date_to):
    """
    OrderItem queryset restricted to orders that were physically delivered
    in [date_from, date_to].  We filter by ShipmentOrder.delivered_at
    (not Order.submitted_at) so revenue is attributed to the delivery date,
    not the order date.
    """
    return OrderItem.objects.filter(
        order__supplier=supplier,
        order__status=OrderStatus.DELIVERED,
        order__shipment_assignments__delivery_status=DeliveryStatus.DELIVERED,
        **{f'{_DELIVERED_AT}__date__gte': date_from,
           f'{_DELIVERED_AT}__date__lte': date_to},
    )


def _delivered_orders(supplier, date_from, date_to):
    """Order queryset with the same delivery-date filter as _delivered_items."""
    return Order.objects.filter(
        supplier=supplier,
        status=OrderStatus.DELIVERED,
        shipment_assignments__delivery_status=DeliveryStatus.DELIVERED,
        shipment_assignments__delivered_at__date__gte=date_from,
        shipment_assignments__delivered_at__date__lte=date_to,
    )


def get_kpis(supplier, date_from, date_to):
    """Return KPI dict. Uses 3 queries."""
    agg = _delivered_items(supplier, date_from, date_to).aggregate(
        revenue=Coalesce(Sum(_LINE_REVENUE), Value(_ZERO), output_field=_DF),
        gross_profit=Coalesce(Sum(_LINE_PROFIT), Value(_ZERO), output_field=_DF),
    )

    # distinct=True guards against any edge-case where an order has multiple
    # ShipmentOrder rows (e.g. reassigned shipments) producing join duplicates.
    order_agg = _delivered_orders(supplier, date_from, date_to).aggregate(
        clients_served=Count('client', distinct=True),
        deliveries_made=Count('id', distinct=True),
    )

    total_expenses = Expense.objects.filter(
        supplier=supplier,
        date__gte=date_from,
        date__lte=date_to,
    ).aggregate(
        total=Coalesce(Sum('amount'), Value(_ZERO), output_field=_DF),
    )['total']

    gross_profit = agg['gross_profit']
    return {
        'revenue': agg['revenue'],
        'gross_profit': gross_profit,
        'total_expenses': total_expenses,
        'net_profit': gross_profit - total_expenses,
        'clients_served': order_agg['clients_served'] or 0,
        'deliveries_made': order_agg['deliveries_made'] or 0,
    }


def get_revenue_over_time(supplier, date_from, date_to):
    """
    Return [{'date': str, 'revenue': float}, ...].
    Time axis = delivery date (ShipmentOrder.delivered_at).
    Bucket granularity: day (≤31 days), week (≤90 days), month (>90 days).
    1 query.
    """
    days = (date_to - date_from).days
    tz_info = django_tz.get_current_timezone()
    if days <= 31:
        trunc_fn = TruncDay(_DELIVERED_AT, tzinfo=tz_info)
        fmt = '%d.%m'
    elif days <= 90:
        trunc_fn = TruncWeek(_DELIVERED_AT, tzinfo=tz_info)
        fmt = '%d.%m'
    else:
        trunc_fn = TruncMonth(_DELIVERED_AT, tzinfo=tz_info)
        fmt = '%m.%Y'

    rows = (
        _delivered_items(supplier, date_from, date_to)
        .annotate(bucket=trunc_fn)
        .values('bucket')
        .annotate(revenue=Coalesce(Sum(_LINE_REVENUE), Value(_ZERO), output_field=_DF))
        .order_by('bucket')
    )
    return [
        {'date': row['bucket'].strftime(fmt), 'revenue': float(row['revenue'])}
        for row in rows
        if row['bucket'] is not None
    ]


def get_top_items(supplier, date_from, date_to, limit=10):
    """Return top items by revenue. 1 query."""
    rows = (
        _delivered_items(supplier, date_from, date_to)
        .values('item_name')
        .annotate(
            revenue=Coalesce(Sum(_LINE_REVENUE), Value(_ZERO), output_field=_DF),
            quantity=Coalesce(
                Sum('quantity'), Value(_ZERO),
                output_field=DecimalField(max_digits=12, decimal_places=3),
            ),
        )
        .order_by('-revenue')[:limit]
    )
    return [
        {'name': r['item_name'], 'revenue': float(r['revenue']), 'quantity': float(r['quantity'])}
        for r in rows
    ]


def get_top_clients(supplier, date_from, date_to, limit=10):
    """Return top clients by revenue. 1 query."""
    rows = (
        _delivered_items(supplier, date_from, date_to)
        .values('order__client__company_name')
        .annotate(revenue=Coalesce(Sum(_LINE_REVENUE), Value(_ZERO), output_field=_DF))
        .order_by('-revenue')[:limit]
    )
    return [
        {'company_name': r['order__client__company_name'], 'revenue': float(r['revenue'])}
        for r in rows
    ]


def get_per_client_breakdown(supplier, date_from, date_to):
    """
    Per-client breakdown for the period.  3 queries.
    - revenue / gross_profit: from orders delivered in the period
    - order_count: distinct orders delivered in the period
    - total_paid: payment records received (date-stamped) in the period
    - outstanding: period revenue minus period payments (period cash-flow balance)
    All numeric values are Python floats for direct JSON serialisation.
    """
    item_rows = list(
        _delivered_items(supplier, date_from, date_to)
        .values('order__client_id', 'order__client__company_name')
        .annotate(
            revenue=Coalesce(Sum(_LINE_REVENUE), Value(_ZERO), output_field=_DF),
            gross_profit=Coalesce(Sum(_LINE_PROFIT), Value(_ZERO), output_field=_DF),
        )
    )

    by_client = {
        row['order__client_id']: {
            'company_name': row['order__client__company_name'],
            'revenue': float(row['revenue']),
            'gross_profit': float(row['gross_profit']),
            'order_count': 0,
            'total_paid': 0.0,
        }
        for row in item_rows
    }

    if not by_client:
        return []

    for row in (
        _delivered_orders(supplier, date_from, date_to)
        .values('client_id')
        .annotate(cnt=Count('id', distinct=True))
    ):
        cid = row['client_id']
        if cid in by_client:
            by_client[cid]['order_count'] = row['cnt']

    for row in (
        PaymentRecord.objects.filter(
            supplier=supplier,
            client_id__in=list(by_client.keys()),
            date__gte=date_from,
            date__lte=date_to,
        )
        .values('client_id')
        .annotate(total=Coalesce(Sum('amount'), Value(_ZERO), output_field=_DF))
    ):
        cid = row['client_id']
        if cid in by_client:
            by_client[cid]['total_paid'] = float(row['total'])

    result = []
    for data in by_client.values():
        data['outstanding'] = round(data['revenue'] - data['total_paid'], 2)
        result.append(data)

    return sorted(result, key=lambda d: d['revenue'], reverse=True)
