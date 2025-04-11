import traceback
from django.db.models import Prefetch
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from booket.models import Provider, ServiceType, ProviderServer, ProviderServerService
from django.contrib.auth.models import User
import logging
from booket.models import Service

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


def get_service_type(id: int, user: User) -> dict:
    """Get Service Type object for given id."""
    try:
        st = get_object_or_404(ServiceType, id=id)
        if st.provider.owner == user:
            context_data = {
                "service_type": st,
            }
        else:
            context_data = {
                "success": False,
                "error": f"You have no rights to modify service type {id}"
            }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def edit_service_type(request: HttpRequest) -> dict:
    try:
        st = get_object_or_404(ServiceType, id=request.POST.get("id"))
        if st.provider.owner == request.user:
            st.name = request.POST.get("name")
            st.name_uz = request.POST.get("name_uz")
            st.name_ru = request.POST.get("name_ru")
            st.is_active = request.POST.get("is_active") == "True"
            st.save()
            context_data = {
                "success": True,
                "st": st,
            }
        else:
            context_data = {
                "success": False,
                "error": f"You have no rights to modify service type {st.id}"
            }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def get_service_list_by_type(type_id: int, user: User) -> dict:
    try:
        st = ServiceType.objects.get(id=type_id, provider__owner=user)
        sl = Service.objects.filter(tip=st)
        context_data = {
            "service_list": sl,
            "service_type": st,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def add_service(request: HttpRequest) -> dict:
    try:
        st = get_object_or_404(ServiceType, id=request.POST.get("type_id"), provider__owner=request.user)
        sr = Service.objects.create(
            tip=st,
            name=request.POST.get("name"),
            name_uz=request.POST.get("name_uz"),
            name_ru=request.POST.get("name_ru"),
            description=request.POST.get("description"),
            price=request.POST.get("price"),
        )
        context_data = {
            "success": True,
            "sr": sr,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e),
            "name": request.POST.get("name"),
            "name_uz": request.POST.get("name_uz"),
            "name_ru": request.POST.get("name_ru"),
            "description": request.POST.get("description"),
            "price": request.POST.get("price"),
            "service_type": st,
        }
        logger.error(traceback.format_exc())
    return context_data


def get_service(id: int, user: User) -> dict:
    try:
        sv = get_object_or_404(Service, id=id, tip__provider__owner=user)
        st_list = ServiceType.objects.filter(provider__owner=user)
        context_data = {
            "service": sv,
            "service_type_list": st_list,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def edit_service(request: HttpRequest) -> dict:
    try:
        sv = get_object_or_404(Service, id=request.POST.get("id"), tip__provider__owner=request.user)
        sv.name = request.POST.get("name")
        sv.name_uz = request.POST.get("name_uz")
        sv.name_ru = request.POST.get("name_ru")
        sv.description = request.POST.get("description")
        sv.price = request.POST.get("price")
        sv.is_active = request.POST.get("is_active") == "True"
        sv.save()
        context_data = {
            "success": True,
            "service": sv,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e),
        }
        logger.error(traceback.format_exc())
    return context_data


def get_server_services(p_server_id: int, user: User) -> dict:
    try:
        # all available service types of the provider and related services
        p_service_types = ServiceType.objects.filter(provider__owner=user).prefetch_related(
            Prefetch(
                'service_set',
                queryset=Service.objects.filter(tip__provider__owner=user).prefetch_related(
                    Prefetch(
                        'providerserverservice_set',
                        queryset=ProviderServerService.objects.filter(provider_server__server_id=p_server_id),
                        to_attr='assigned_service',
                    )
                )
            )
        )
        p_s_services = ProviderServerService.objects.filter(
            provider_server_id=p_server_id
        )
        context_data = {
            "service_types": p_service_types,
            "assigned_services": p_s_services,
            "p_server_id": p_server_id,
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data


def edit_server_service(request: HttpRequest) -> dict:
    try:
        sr_type = ServiceType.objects.get(
            id=request.POST.get("service_type_id"),
            provider__owner=request.user
        )
        if request.POST.get("is_active") is None:
            ProviderServerService.objects.filter(
                id=request.POST.get("p_s_service_id"),
            ).delete()
        else:
            p_s_server = ProviderServer.objects.get(
                id=request.POST.get("provider_server_id"),
            )
            service = get_object_or_404(
                Service,
                id=request.POST.get("service_id"),
                tip=sr_type,
            )
            private_price = request.POST.get("private_price")
            if private_price == 0 or private_price == "":
                private_price = None
            provider_server_service, is_created = ProviderServerService.objects.update_or_create(
                provider_server=p_s_server,
                service=service,
                defaults={
                    "service_private_price": private_price,
                }
            )
        context_data = {
            "success": True,
            "p_server_id": request.POST.get("provider_server_id"),
        }
    except Exception as e:
        context_data = {
            "success": False,
            "error": str(e)
        }
        logger.error(traceback.format_exc())
    return context_data
