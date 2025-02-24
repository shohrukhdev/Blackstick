from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render, redirect
from difflib import get_close_matches

from booket.models import Provider


def main_page(request, identifier: str):
    if request.method == "GET":
        try:
            provider = Provider.objects.get(identifier=identifier)
        except Provider.DoesNotExist:
            # Check if identifiers are in the cache
            cache_key = "all_provider_identifiers"
            all_identifiers = cache.get(cache_key)

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
        return render(request, "booket/client/main.html")
