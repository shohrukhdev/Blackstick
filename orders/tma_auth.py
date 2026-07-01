import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, unquote


def verify_init_data(init_data_raw: str, bot_token: str, max_age_seconds: int = 3600) -> dict:
    """
    Verify Telegram WebApp initData HMAC per Telegram docs.
    Returns parsed data dict (with 'user' as a dict) if valid.
    Raises ValueError with a reason string if invalid.
    """
    params = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    received_hash = params.pop('hash', None)
    if not received_hash:
        raise ValueError('No hash in initData')

    auth_date = int(params.get('auth_date', 0))
    if time.time() - auth_date > max_age_seconds:
        raise ValueError('initData expired')

    # Data-check string: sorted key=value lines, \n-joined (hash excluded)
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(params.items()))

    # secret_key = HMAC-SHA256(key="WebAppData", data=bot_token)
    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError('initData signature mismatch')

    result = dict(params)
    if 'user' in result:
        result['user'] = json.loads(unquote(result['user']))

    return result
