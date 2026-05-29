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
    """
    Auto-resolve appointments whose end_datetime has passed:
      - NEW (OTP never confirmed) → CANCELLED
      - CONFIRMED / PENDING / ACCEPTED → COMPLETED

    days_back: when > 0, restrict to appointments created within the last N days.
    When 0 (default), processes all matching appointments regardless of age.
    """
    now = timezone.now()
    base_filter = {}
    if days_back > 0:
        base_filter["created_on__date__gte"] = now.date() - timedelta(days=days_back)

    try:
        cancelled_count = Appointment.objects.filter(
            **base_filter,
            status="NEW",
            end_datetime__lt=now,
        ).update(status="CANCELLED")

        to_complete = Appointment.objects.filter(
            **base_filter,
            status__in=["CONFIRMED", "PENDING", "ACCEPTED"],
            end_datetime__lt=now,
        )
        completed_count = 0
        for appointment in to_complete:
            total = appointment.compute_total()
            appointment.status = "COMPLETED"
            appointment.total_amount = total
            appointment.paid_amount = total
            appointment.save(update_fields=["status", "total_amount", "paid_amount"])
            completed_count += 1

        logger.info(
            f"[complete_old_appointments] {cancelled_count} unconfirmed → CANCELLED, "
            f"{completed_count} past → COMPLETED."
        )
        return cancelled_count + completed_count

    except Exception as e:
        logger.error(f"[complete_old_appointments] Error: {str(e)}", exc_info=True)
        return 0


def is_demo_provider(provider_identifier: str):
    """Check if the provider is a demo provider."""
    return provider_identifier in DEMO_PROVIDERS
