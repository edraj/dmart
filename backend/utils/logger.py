import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from pythonjsonlogger.jsonlogger import JsonFormatter
from utils.settings import settings


class CustomFormatter(JsonFormatter):
    def __init__(self):
        super().__init__(
            "%(levelname)s %(asctime) %(threadName)s %(pathname)s %(lineno)s %(funcName)s %(message)s"
        )


class CustomHandler(ConcurrentRotatingFileHandler):
    def __init__(
            self, filename, mode='a', maxBytes=1048576, backupCount=5,
            encoding=None, debug=False, delay=None, use_gzip=True,
            owner=None, chmod=None, umask=None, newline=None, terminator="\n",
            unicode_error_policy='ignore',
    ):
        super().__init__(
            filename, 
            mode=mode, 
            maxBytes=maxBytes, 
            backupCount=backupCount, 
            encoding=encoding, 
            debug=debug, 
            delay=delay, 
            use_gzip=use_gzip, 
            owner=owner, 
            chmod=chmod, 
            umask=umask, 
            newline=newline, 
            terminator=terminator, 
            unicode_error_policy=unicode_error_policy
        )


def getLogger(log_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger(settings.app_name or "dmart")
    handler = CustomHandler(log_file or settings.log_file)
    handler.setFormatter(CustomFormatter())
    logger.addHandler(handler)
    return logger


