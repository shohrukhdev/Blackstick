import logging

from cryptography.fernet import Fernet
import time

from Blackstick.settings import FERNET_KEY

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


def valid_signature(signature: str, expiry_seconds: int = 600) -> bool:
    """
    Decrypt and validate the signature.
    """
    try:
        decrypted_data = cipher.decrypt(signature.encode()).decode()
        provider_id, timestamp_str = decrypted_data.split(":")
        timestamp = int(timestamp_str)

        if time.time() - timestamp > expiry_seconds:
            return False  # Expired

        return True  # Valid signature
    except Exception as e:
        logger.error(f"Invalid or expired signature. Error: {e}")
        return False  # Decryption failed (tampered or expired)
