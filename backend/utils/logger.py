import json
import logging
import logging.config
from utils.settings import settings


class CustomFormatter(logging.Formatter):
    def format(self, record):
        correlation_id = getattr(record, "correlation_id", "")
        if correlation_id == "ROOT" and getattr(record, "props", None):
            correlation_id = getattr(record, "props", {})\
                .get("response", {}).get("headers", {}).get("x-correlation-id", "")
        data = {
            "correlation_id": correlation_id,
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "props": getattr(record, "props", ""),
            "thread": record.threadName,
            "process": record.process,
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
        }
        return json.dumps(data)


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
            "maxBytes": 1048576,
            "use_gzip": True,
            "formatter": "json",
        },
    },
    "loggers": {
        "fastapi": {
            "handlers": settings.log_handlers,
            "level": logging.INFO,
            "propagate": True,
        }
    },
}


def changeLogFile(log_file: str | None = None) -> None:
    global logging_schema
    if (log_file and "handlers" in logging_schema and "file" in logging_schema["handlers"] 
        and "filename" in logging_schema["handlers"]["file"]):
        logging_schema["handlers"]["file"]["filename"] = log_file
