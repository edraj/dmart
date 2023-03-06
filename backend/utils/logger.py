import logging
import logging.handlers
from utils.settings import settings
from concurrent_log_handler import ConcurrentRotatingFileHandler

logger = logging.getLogger(settings.app_name)
logger.setLevel(logging.INFO)
log_handler = ConcurrentRotatingFileHandler(
    f"{settings.log_path}/x-ljson.log", "a", 100_000_000, 1000
)
logger.addHandler(log_handler)

# json_logger = logging.getLogger(settings.app_name)
# json_logger.setLevel(logging.INFO)
