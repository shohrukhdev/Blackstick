import logging
from datetime import timedelta

from cryptography.fernet import Fernet
import time

from django.http import HttpRequest
from django.utils import timezone

from Blackstick.settings import FERNET_KEY
from booket.constants import DEMO_PROVIDERS
from booket.models import Appointment

logger = logging.getLogger(__name__)
cipher = Fernet(FERNET_KEY)


def generate_signature(provider_id: int) -> str:
    """
    Encrypt the provider_id and timestamp using AES (Fernet).
    """
    timestamp = int(time.time())  # Current Unix timestamp
    data = f"{provider_id}:{timestamp}".encode()
    encrypted_data = cipher.encrypt(data)  # AES Encryption
    return encrypted_data.decode()


def valid_signature(request: HttpRequest, expiry_seconds: int = 600) -> bool:
    """
    Extracts X-Signature from headers, decrypts, and validates it.
    """
    signature = request.headers.get("X-Signature")
    if not signature:
        logger.error(f"X-Signature is missing. request: {request.META}")
        return False  # No signature provided

    try:
        decrypted_data = cipher.decrypt(signature.encode()).decode()
        provider_id, timestamp_str = decrypted_data.split(":")
        timestamp = int(timestamp_str)

        if time.time() - timestamp > expiry_seconds:
            logger.error(f"X-Signature expired. request: {request.META}")
            return False  # Expired

        return True  # Valid signature
    except Exception:
        logger.error(f"X-Signature malformed. request: {request.META}")
        return False  # Decryption failed (tampered or expired)


def mask_email(email):
    """Masks an email address, showing only the first character and domain."""
    if not email:
        return ""
    parts = email.split("@")
    if len(parts) != 2:
        return email  # Return original if not a valid email
    local_part = parts[0]
    domain = parts[1]
    masked_local = local_part[0] + "*" * (len(local_part) - 1) if len(local_part) > 1 else local_part
    return f"{masked_local}@{domain}"


def mask_phone_number(phone_number):
    """Masks a phone number, showing only the first and last two digits."""
    if not phone_number:
        return ""
    if len(phone_number) < 4:
        return phone_number  # Return original if too short
    return phone_number[0] + "*" * (len(phone_number) - 3) + phone_number[-2:]


def complete_old_appointments(days_back: int = 0):
    """Mark old appointments as COMPLETED."""
    now = timezone.now()
    today = now.date()

    if days_back > 0:
        created_after = today - timedelta(days=days_back)
    else:
        created_after = today

    statuses_to_check = ["CONFIRMED", "PENDING", "ACCEPTED"]

    try:
        appointments = Appointment.objects.filter(
            created_on__date__gte=created_after,
            created_on__date__lte=today,
            status__in=statuses_to_check,
            end_datetime__lt=now
        )

        updated_count = appointments.update(status="COMPLETED")

        logger.info(f"[Appointment Completion Task] ✅ Updated {updated_count} appointment(s) to COMPLETED.")
        return updated_count

    except Exception as e:
        logger.error(f"[Appointment Completion Task] ❌ Error while updating appointments: {str(e)}", exc_info=True)
        return 0


def is_demo_provider(provider_identifier: str):
    """Check if the provider is a demo provider."""
    return provider_identifier in DEMO_PROVIDERS
