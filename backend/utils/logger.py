import json
import logging
import logging.config
from utils.settings import settings


class CustomFormatter(logging.Formatter):
    def format(self, record):
        data = {
            'time': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'props': getattr(record, "props", ""),
            "thread": record.threadName,
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
        }
        return json.dumps(data)


logging_schema = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': CustomFormatter
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': settings.log_file,
            'formatter': 'json'
        }
    },
    'loggers': {
        'fastapi': {
            'handlers': ['file'],
            'level': logging.INFO,
            'propagate': True
        }
    }
}

def changeLogFile(log_file: str | None = None) -> None:
    global logging_schema
    if log_file:
        logging_schema["handlers"]["file"]["filename"] = log_file