from __future__ import annotations

import json
import logging
import logging.config
import os
from typing import Any, Dict

from utils.settings import settings
from utils.masking import mask_sensitive_data

class CustomFormatter(logging.Formatter):
    """
    Emits one JSON line with this exact key order:
    correlation_id, time, level, message, props, thread, process
    """
    def __init__(self) -> None:
        log_dir = os.path.dirname(settings.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:  # type: ignore
        correlation_id = getattr(record, "correlation_id", "")
        props = getattr(record, "props", "") or ""

        if correlation_id == "ROOT" and isinstance(props, dict):
            try:
                resp_headers = props.get("response", {}).get("headers", {}) or {}
                correlation_id = (
                    resp_headers.get("correlation_id")
                    or resp_headers.get("x-correlation-id")
                    or correlation_id
                )
            except Exception:
                pass

        if isinstance(record.msg, dict):
            safe_message: Any = mask_sensitive_data(record.msg)
        else:
            safe_message = record.getMessage()

        if isinstance(props, dict):
            safe_props: Any = mask_sensitive_data(props)
        else:
            safe_props = props

        out: Dict[str, Any] = {
            "correlation_id": correlation_id,
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": safe_message,
            "props": safe_props,
            "thread": record.threadName,
            "process": record.process,
        }

        return json.dumps(out, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


logging_schema: Dict[str, Any] = {
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
