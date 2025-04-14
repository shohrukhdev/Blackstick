import httpx
import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://notify.eskiz.uz/api"


def get_sms_api_token() -> str | None:
    """
    Authenticates with Eskiz and returns the Bearer token.
    Caches the token for 29 days (slightly less than 30 days to be safe).
    """
    # Check if token is already cached
    token = cache.get("eskiz_api_token")
    LOGIN_URL = f"{BASE_URL}/auth/login"
    if token:
        return token

    # Token not in cache, authenticate
    try:
        with httpx.Client() as client:
            response = client.post(
                LOGIN_URL,
                data={
                    "email": settings.ESKIZ_EMAIL,
                    "password": settings.ESKIZ_PASSWORD
                },
                timeout=10
            )

            if response.status_code == 200:
                res_data = response.json()
                token = res_data["data"]["token"]
                cache.set("eskiz_api_token", token, timeout=60 * 60 * 24 * 29)  # Cache for 29 days
                logger.info("Eskiz token successfully retrieved and cached.")
                return token
            else:
                logger.warning(f"Failed to get Eskiz token: {response.text}")
                return None
    except Exception as e:
        logger.exception(f"Exception while getting Eskiz token: {e}")
        return None


def refresh_sms_api_token() -> str | None:
    """
        Refreshes the Eskiz token using the current token.
        If successful, replaces the cached token.
        """
    current_token = cache.get("eskiz_api_token")
    if not current_token:
        logger.warning("No token to refresh, please login first.")
        return None

    try:
        response = httpx.patch(
            f"{BASE_URL}/auth/refresh",
            headers={
                "Authorization": f"Bearer {current_token}"
            },
            timeout=10
        )

        if response.status_code == 200:
            res_data = response.json()
            new_token = res_data["data"]["token"]
            cache.set("eskiz_api_token", new_token, timeout=60 * 60 * 24 * 29)
            logger.info("Eskiz token refreshed and cached.")
            return new_token
        else:
            logger.warning(f"Failed to refresh token: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Exception while refreshing Eskiz token: {e}")
        return None


def eskiz_authenticated_request(method: str, url: str, **kwargs) -> httpx.Response | None:
    """
    Makes an authenticated request to Eskiz API with retry on 401 (unauthorized).
    If token is missing or expired, attempts to re-authenticate.
    """
    token = cache.get("eskiz_sms_token")
    if not token:
        token = get_sms_api_token()
        if not token:
            logger.error("Failed to get token for Eskiz API request.")
            return None

    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            logger.warning("Eskiz token expired or invalid. Re-authenticating...")
            token = get_sms_api_token()
            if not token:
                logger.error("Token refresh failed.")
                return None

            headers["Authorization"] = f"Bearer {token}"
            response = httpx.request(method, url, headers=headers, **kwargs)

        return response

    except Exception as e:
        logger.exception(f"Eskiz API {method} request failed: {e}")
        return None


def get_sms_user_data() -> dict | None:
    """
    Fetches the authenticated user profile info from Eskiz.
    """
    response = eskiz_authenticated_request("GET", f"{BASE_URL}/auth/user")

    if response and response.status_code == 200:
        return response.json()

    logger.warning("Could not retrieve user data from Eskiz.")
    return None


def send_sms(
    phone_number: str,
    message: str,
    from_id: str = "4546",
    callback_url: str | None = None
) -> dict | None:
    """
    Sends a single SMS via Eskiz API.
    - phone_number: in format '998901234567'
    - message: SMS body text
    - from_id: Sender ID (default: '4546')
    - callback_url: optional webhook to receive delivery status

    Returns:
        dict response from Eskiz or None on failure
    """
    data = {
        "mobile_phone": phone_number,
        "message": message,
        "from": from_id,
    }

    if callback_url:
        data["callback_url"] = callback_url

    try:
        token = cache.get("eskiz_sms_token")
        if not token:
            token = get_sms_api_token()
            if not token:
                logger.error("Failed to get Eskiz token before sending SMS.")
                return None

        headers = {"Authorization": f"Bearer {token}"}

        response = httpx.post(
            f"{BASE_URL}/message/sms/send",
            data=data,
            headers=headers,
            timeout=15,
        )

        if response.status_code == 401:
            logger.info("Eskiz token expired. Re-authenticating...")
            token = get_sms_api_token()
            if not token:
                return None
            headers["Authorization"] = f"Bearer {token}"

            response = httpx.post(
                f"{BASE_URL}/message/sms/send",
                data=data,
                headers=headers,
                timeout=15,
            )

        if response.status_code == 200:
            logger.info(f"SMS sent to {phone_number}.")
            return response.json()

        logger.warning(f"Failed to send SMS: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        logger.exception(f"Exception while sending SMS: {e}")
        return None
