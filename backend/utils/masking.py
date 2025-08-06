# utils/masking.py
import re
from typing import Any

def mask_sensitive_data(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: mask_sensitive_data(v) if k.lower() not in {
                'password', 'access_token', 'refresh_token', 'auth_token', 'jwt', 'otp', 'code', 'token'
            } else '******'
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    elif isinstance(data, str) and any(word in data.lower() for word in {
        'auth_token', 'access_token', 'refresh_token', 'jwt', 'otp', 'token'
    }):
        return '******'
    return data
