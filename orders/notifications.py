import logging

logger = logging.getLogger(__name__)


def notify_supplier_new_order(order):
    """Stub — fully implemented in Task 16 with Celery + Telegram."""
    pass


def notify_client_order_accepted(order):
    """Stub — Task 16."""
    pass


def notify_client_order_declined(order):
    """Stub — Task 16."""
    pass


def notify_client_prices_adjusted(order):
    """Stub — Task 16."""
    pass


def notify_client_order_dispatched(order):
    """Stub — Task 16."""
    pass


def notify_client_order_delivered(order):
    """Stub — Task 16."""
    pass
