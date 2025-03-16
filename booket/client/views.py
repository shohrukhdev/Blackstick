from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from difflib import get_close_matches

from django.views.decorators.csrf import csrf_protect

from booket.models import Provider, Client
from booket.utils import generate_signature, validate_signature


def main_page(request, identifier: str):
    if request.method == "GET":
        try:
            provider = Provider.objects.get(identifier=identifier)
        except Provider.DoesNotExist:
            # Check if identifiers are in the cache
            cache_key = "all_provider_identifiers"
            all_identifiers = cache.get(cache_key, )

            # If not in cache, fetch from the database and store in cache
            if all_identifiers is None:
                all_identifiers = list(Provider.objects.values_list('identifier', flat=True))
                cache.set(cache_key, all_identifiers, timeout=60 * 60)  # Cache for 1 hour

            # Find the closest match with a maximum of 4 differences
            close_matches = get_close_matches(identifier, all_identifiers, n=1, cutoff=0.2)

            if close_matches and len(close_matches[0]) - len(identifier) <= 4:
                # Get the provider with the closest match
                provider = Provider.objects.get(identifier=close_matches[0])
                return redirect(f"/{provider.identifier}/")
            else:
                # If no close match or difference is more than 4 characters, return 404
                return render(request, "404.html", status=404)
        signature = generate_signature(provider.id)
        return render(request, "booket/client/main.html", context={"provider": provider, "signature": signature})


def get_server_details(p_server_id: int):
    pass


def get_client_data(request):
    """Get client data to check if it exists."""
    response = {}
    if request.method == "GET" and validate_signature(request):
        phone_number = request.GET.get("phone_number")
        email = request.GET.get("email")
        try:
            if phone_number:
                client = Client.objects.get(phone_number=phone_number)
            elif email:
                client = Client.objects.get(email=email)
            else:
                raise ValidationError("Not a valid phone or email")
            response["success"] = True
            response["client_id"] = client.id
            response["client_email"] = client.email
            response["client_phone"] = client.phone_number
            response["client_full_name"] = client.full_name
            response["client_sex"] = client.sex

            return JsonResponse(response)
        except Client.DoesNotExist:
            response["success"] = False
            response["error"] = "Client does not exist"
        except Exception as e:
            response["success"] = False
            response["error"] = str(e)
        return JsonResponse(response)
