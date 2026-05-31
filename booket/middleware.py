import json
import ipaddress
import logging
from urllib.request import urlopen
from urllib.error import URLError

from django.conf import settings
from django.utils.translation import activate

logger = logging.getLogger(__name__)

# CIS / post-Soviet countries where Russian is the common lingua franca.
RU_COUNTRIES = frozenset({
    'RU',  # Russia
    'KZ',  # Kazakhstan
    'BY',  # Belarus
    'UA',  # Ukraine
    'KG',  # Kyrgyzstan
    'TJ',  # Tajikistan
    'TM',  # Turkmenistan
    'MD',  # Moldova
    'AM',  # Armenia
    'AZ',  # Azerbaijan
})

_CACHE_TTL = 60 * 60 * 24  # cache IP→country for 24 hours


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _is_routable(ip):
    """Return True only for public, routable IPs worth looking up."""
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_unspecified)
    except ValueError:
        return False


def _country_for_ip(ip):
    """
    Return ISO-3166-1 alpha-2 country code for a public IP.
    Uses ip-api.com (free, no key, 45 req/min).
    Caches result in Django's cache backend for 24 h.
    """
    from django.core.cache import cache

    key = f'geo:cc:{ip}'
    country = cache.get(key)
    if country is not None:
        return country

    try:
        url = f'http://ip-api.com/json/{ip}?fields=countryCode'
        with urlopen(url, timeout=1.0) as resp:
            data = json.loads(resp.read().decode())
        country = data.get('countryCode', '')
    except (URLError, OSError, ValueError):
        logger.debug('GeoLanguageMiddleware: lookup failed for %s', ip)
        return ''

    cache.set(key, country, _CACHE_TTL)
    return country


def _lang_for_country(country):
    if country == 'UZ':
        return 'uz'
    if country in RU_COUNTRIES:
        return 'ru'
    return 'en'


class GeoLanguageMiddleware:
    """
    Automatically activate a language on first visit based on the visitor's
    geographic location (IP → country → language):

        Uzbekistan          →  uz
        CIS / post-Soviet   →  ru
        Everywhere else     →  en

    Runs *after* LocaleMiddleware.  If the visitor already has the
    'django_language' cookie (they chose a language manually), this middleware
    does nothing so the explicit preference is always respected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        detected = None

        # Only fire when no explicit language cookie is present
        if not request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            ip = _client_ip(request)
            if _is_routable(ip):
                country = _country_for_ip(ip)
                if country:
                    detected = _lang_for_country(country)

            # Activate the detected language so the view and templates use it
            if detected:
                activate(detected)
                request.LANGUAGE_CODE = detected

        response = self.get_response(request)

        # Persist the detected language as a cookie so future requests
        # are handled by LocaleMiddleware without another lookup
        if detected:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                detected,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                secure=settings.LANGUAGE_COOKIE_SECURE,
                httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )

        return response
