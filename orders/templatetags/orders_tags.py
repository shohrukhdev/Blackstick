from django import template

register = template.Library()


@register.filter
def unit_step(unit):  # noqa: unused-arg — kept for template compatibility, always 1
    return 1


@register.filter
def uz_money(value):
    """Format a number with narrow no-break space thousands separator. 12500 -> '12 500'"""
    try:
        rounded = int(round(float(str(value))))
        return f'{rounded:,}'.replace(',', ' ')
    except (ValueError, TypeError):
        return value


@register.filter
def js_price(value):
    """Return a plain integer safe for embedding in JS (no locale formatting)."""
    try:
        return int(round(float(str(value))))
    except (ValueError, TypeError):
        return 0


@register.filter
def desc_size_class(description):
    """Pick the largest Tailwind text size that realistically fits in a square card image."""
    n = len(description) if description else 0
    if n <= 20:
        return 'text-2xl font-bold leading-tight'
    if n <= 40:
        return 'text-xl font-bold leading-tight'
    if n <= 80:
        return 'text-base font-semibold leading-snug'
    if n <= 160:
        return 'text-sm font-medium leading-snug'
    return 'text-xs font-medium leading-relaxed'


@register.filter
def unit_uz(unit_code):
    """Convert a unit code ('kg', 'piece', …) to its Uzbek display label."""
    from orders.constants import UNIT_LABELS
    return UNIT_LABELS.get(unit_code, unit_code)


@register.filter
def status_badge_class(status):
    """Return Tailwind badge classes for an OrderStatus value."""
    mapping = {
        'SUBMITTED': 'bg-blue-100 text-blue-700',
        'ACCEPTED': 'bg-green-100 text-green-700',
        'DECLINED': 'bg-red-100 text-red-700',
        'IN_SHIPMENT': 'bg-amber-100 text-amber-700',
        'DELIVERED': 'bg-emerald-100 text-emerald-700',
        'DRAFT': 'bg-gray-100 text-gray-500',
    }
    return mapping.get(status, 'bg-gray-100 text-gray-500')
