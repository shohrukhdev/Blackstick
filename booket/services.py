from booket.models import Provider, ServiceType
from django.contrib.auth.models import User


def get_owners_provider(user: User) -> Provider:
    """Get Provider object which given user is the owner."""
    return Provider.objects.get(owner=user)


def get_provider_service_types(provider: Provider):
    """Get Service type objects for given provider."""
    return ServiceType.objects.filter(provider=provider)