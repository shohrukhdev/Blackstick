import traceback
from lib2to3.fixes.fix_input import context

from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from booket.models import Provider, ServiceType, Server, ProviderServer
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


def get_owners_provider(user: User) -> dict:
    """Get Provider object which given user is the owner of."""
    try:
        provider = Provider.objects.get(owner=user)
        context_data = {"provider": provider}
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def get_provider_service_types(provider: Provider) -> ServiceType:
    """Get Service type objects for given provider."""
    return ServiceType.objects.filter(provider=provider)


def edit_provider(request: HttpRequest) -> dict:
    """
    Edit Provider object from given request.
    Return context data.
    """
    try:
        provider = get_object_or_404(Provider, id=request.POST.get("provider_id"))
        provider.name = request.POST.get("name")
        provider.address = request.POST.get("address")
        provider.description = request.POST.get("description")
        provider.is_active = request.POST.get("is_active") == "True"
        provider.logo = request.FILES.get("logo", provider.logo)
        provider.save()
        context_data = {
            "success": True,
            "provider": provider,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def get_server_by_id(user: User, server_id: int) -> dict:
    """Get server that belongs to the provider or server with the requesting user."""
    try:
        ps = get_object_or_404(ProviderServer, server_id=server_id)
        if ps.server.user == user or ps.provider.owner == user:
            context_data = {
                "ps": ps,
            }
        else:
            context_data = {
                "success": False,
                "error": f"You have no rights to modify server {server_id}"
            }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())

    return context_data


def edit_server(request: HttpRequest) -> dict:
    """Edit Server object from given request."""
    try:
        ps = get_object_or_404(ProviderServer, id=request.POST.get("id"))

        if ps.server.user == request.user or ps.provider.owner == request.user:
            ps.server.phone_number = request.POST.get("phone_number")
            ps.server.info = request.POST.get("info")
            ps.server.is_active = request.POST.get("is_active") == "True"
            ps.server.image = request.FILES.get("image", ps.server.image)
            ps.server.save()
            context_data = {
                "ps": ps,
                "success": True,
            }
        else:
            context_data = {
                "success": False,
                "error": f"You have no rights to modify server {ps.server.id}"
            }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def add_service_type(request: HttpRequest) -> dict:
    """Add Service Type object for given request."""
    try:
        provider = Provider.objects.get(owner=request.user)
        st = ServiceType.objects.create(
            name=request.POST.get("name"),
            name_uz=request.POST.get("name_uz"),
            name_ru=request.POST.get("name_ru"),
            provider=provider,
        )
        context_data = {
            "success": True,
            "service_type": st,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data
