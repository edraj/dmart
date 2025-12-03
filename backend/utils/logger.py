import re
import json
import logging
import os

from utils.settings import settings
import socket


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        return str(o)


COMBINED_SENSITIVE_PATTERN = re.compile(
    r'(?i)(?:'
    r'(your\s+otp\s+code\s+is\s+)\d{4,8}|'
    r'(otp\s+for\s+\d+\s+is\s+)\d{4,8}|'
    r'(zip\s+pw\s+for\s+\d+\s+is\s+)[a-f0-9]{6,}|'
    r'(your\s+password\s+for\s+the\s+export\s+zip\s+is\s+)[a-f0-9]{6,}|'
    r'(invitation=)[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|'
    r'("pin"\s*:\s*)"[^"]*"|'
    r'("authorization"\s*:\s*)"[^"]*"|'
    r'("auth_token"\s*:\s*)"[^"]*"|'
    r'("firebase_token"\s*:\s*)"[^"]*"|'
    r'("evd-device-id"\s*:\s*)"[^"]*"|'
    r'("access_token"\s*:\s*)"[^"]*"|'
    r'("cookie"\s*:\s*)"[^"]*"|'
    r'("set-cookie"\s*:\s*)"[^"]*"'
    r')'
)


SENSITIVE_KEYWORDS = ("authorization", "token", "password", "otp", "pin", "cookie", "auth", "firebase_token",
                      "evd-device-id")


def mask_replacement(match):
    """Replace matched groups with a general mask."""
    groups = match.groups()
    for i, group in enumerate(groups):
        if group is not None:
            # For JSON format: "key": "value" → "key": "******"
            if '"' in group:
                return group + '"' + ('*' * 6) + '"'
            # For plain format: key: value → key: ******
            else:
                return group + ('*' * 6)
    return match.group(0)


def mask_sensitive_data_string(log_string: str) -> str:
    """Mask sensitive data only if keywords present."""
    if not isinstance(log_string, str):
        return log_string
    # Quick keyword check first (very fast)
    if not any(keyword in log_string.lower() for keyword in SENSITIVE_KEYWORDS):
        return log_string
    # Only apply regex if keywords found
    return COMBINED_SENSITIVE_PATTERN.sub(mask_replacement, log_string)


class CustomFormatter(logging.Formatter):
    """
    Emits one JSON line with this exact key order:
    correlation_id, time, level, message, props, thread, process
    """
    def __init__(self) -> None:
        log_dir = os.path.dirname(settings.log_file)
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        super().__init__()

    def format(self, record):
        correlation_id = getattr(record, "correlation_id", "")
        if correlation_id == "ROOT" and getattr(record, "props", None):
            correlation_id = getattr(record, "props", {})\
                .get("response", {}).get("headers", {}).get("x-correlation-id", "")

        props = getattr(record, "props", {})

        # Extract hostname
        hostname = socket.gethostname()

        data = {
            "hostname": hostname,
            "correlation_id": correlation_id,
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "props": props,
            "thread": record.threadName,
            "process": record.process,
        }
        try:
            log_string = json.dumps(data, cls=JSONEncoder)
            masked_log = mask_sensitive_data_string(log_string)
            return masked_log
        except Exception as e:
            return json.dumps({"error": str(e), "message": record.getMessage()})


logging_schema : dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": "asgi_correlation_id.CorrelationIdFilter",
            "uuid_length": 32,
            "default_value": "ROOT",
        },
    },
    "formatters": {
        "json": {"()": "utils.logger.CustomFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["correlation_id"],
            "level": "INFO",
            "formatter": "json",
            "stream": "ext://sys.stdout",  # Default is stderr
        },
        "file": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "filters": ["correlation_id"],
            "filename": settings.log_file,
            "backupCount": 5,
            "maxBytes": 0x10000000,
            "use_gzip": False,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": settings.log_handlers,
        "level": "INFO",
    },
    "loggers": {
        "fastapi": {
            "handlers": settings.log_handlers,
            "level": logging.INFO,
            "propagate": False,
        },
        "hypercorn": {
            "handlers": settings.log_handlers,
            "level": logging.INFO,
            "propagate": False,
        },
        "hypercorn.error": {
            "handlers": settings.log_handlers,
            "level": logging.INFO,
            "propagate": False,
        },
        "hypercorn.access": {
            "handlers": settings.log_handlers,
            "level": logging.INFO,
            "propagate": False,
        },
    },
}


def changeLogFile(log_file: str | None = None) -> None:
    global logging_schema
    if (log_file and "handlers" in logging_schema and "file" in logging_schema["handlers"] 
        and "filename" in logging_schema["handlers"]["file"]):
        logging_schema["handlers"]["file"]["filename"] = log_file
