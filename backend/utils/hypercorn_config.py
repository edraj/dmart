from os import cpu_count

from fastapi.logger import logger

from utils.logger import logging_schema
from utils.settings import settings

bind = [f"{settings.listening_host}:{settings.listening_port}"]
workers = cpu_count()
backlog = 200
worker_class = "asyncio"
logconfig_dict = logging_schema
errorlog = logger
