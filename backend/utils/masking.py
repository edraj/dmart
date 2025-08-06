import re
from typing import Any

SENSITIVE_KEYS = {
    "password", "pass", "access_token", "refresh_token",
    "auth_token", "otp", "authorization", "token", "jwt"
}

JWT_PATTERN = re.compile(
    r"^[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,}$"
)

LONG_SECRET_PATTERN = re.compile(r"^[0-9]{6,}$")

def mask_sensitive_data(data: Any, parent_key: str = "") -> Any:

    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            key_lower = k.lower()

            if key_lower in SENSITIVE_KEYS:
                masked[k] = "******"
            else:
                masked[k] = mask_sensitive_data(v, parent_key=k)
        return masked

    elif isinstance(data, list):
        return [mask_sensitive_data(item, parent_key=parent_key) for item in data]

    elif isinstance(data, str):
        if JWT_PATTERN.match(data):
            return "******"

        if LONG_SECRET_PATTERN.match(data) and parent_key.lower() in SENSITIVE_KEYS:
            return "******"

        if parent_key.lower() in SENSITIVE_KEYS:
            return "******"

        return data

    return data
