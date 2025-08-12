import json
import logging
import logging.config
import os

from utils.settings import settings
import socket

class CustomFormatter(logging.Formatter):
    def __init__(self):
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
            # "pathname": record.pathname,
            # "lineno": record.lineno,
            # "funcName": record.funcName,
        }
        masked_data = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
        return (masked_data)

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
    "formatters": {"json": {"()": CustomFormatter}},
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
