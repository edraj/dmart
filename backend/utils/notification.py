from abc import ABC, abstractmethod
from importlib.util import find_spec, module_from_spec
import json
import sys
from typing import Any
from pathlib import Path

from models.core import NotificationData
from utils.settings import settings
from models.core import User
from data_adapters.adapter import data_adapter as db
from fastapi.logger import logger


class Notifier(ABC):
    
    @abstractmethod
    async def send(self, data: NotificationData) -> bool:
        pass

    async def _load_user(self, shortname: str) -> Any:
        if not hasattr(self, "user"):

            self.user = await db.load(
                space_name=settings.management_space,
                subpath=settings.users_subpath,
                shortname=shortname,
                class_type=User,
                user_shortname="__system__",
            )
        return self.user


class NotificationManager:

    notifiers: dict[str, Notifier] = {}

    def __init__(self) -> None:
        # Load the notifiers depending on config/notification.json file
        if not self.notifiers:
            config_path = Path(__file__).resolve().parent.parent / "config/notification.json"
            if config_path.exists():
                with open(config_path) as conf_file:
                    conf_data = json.load(conf_file)

                for platform, data in conf_data.items():
                    if not data["active"]:
                        continue

                    module_name = data["module"]
                    module_specs = find_spec(module_name)
                    if not module_specs or not module_specs.loader:
                        continue
                    module = module_from_spec(module_specs)
                    sys.modules[module_name] = module
                    module_specs.loader.exec_module(module)
                    self.notifiers[platform] = getattr(module, data["class"])()

    async def send(self, platform, data: NotificationData) -> bool:
        if platform not in self.notifiers:
            return False
        try:
            await self.notifiers[platform].send(data)
            return True
        except Exception as e:
            logger.warning(
                "Notification",
                extra={
                    "props": {
                        "title": f"FAIL at {self.notifiers[platform]}.send",
                        "message": str(e),
                    }
                },
            )
            return False
