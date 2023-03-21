
from abc import ABC
from importlib.util import find_spec, module_from_spec
import json
import sys
from models.core import Translation
from utils.settings import settings
from models.core import User
from utils.db import load
from fastapi.logger import logger


class NotifierInterface(ABC):
    async def send(
        self, 
        receiver: str, 
        title: Translation, 
        body: Translation, 
        image_urls: Translation | None = None
    ):
        pass

    async def _load_user(self, shortname: str) -> User:
        if not hasattr(self, "user"):
    
            self.user = await load(
                space_name=settings.management_space,
                subpath=settings.users_subpath,
                shortname=shortname,
                class_type=User,
                user_shortname="__system__",
                branch_name=settings.management_space_branch,
            )
        return self.user


class NotificationManager():
    
    notifiers: dict[str, NotifierInterface] = {}
    
    def __init__(self) -> None:
        # Load the notifiers depending on config/notification.json file
        if not self.notifiers:
            with open("config/notification.json") as conf_file:
                conf_data = json.load(conf_file)

            for platform, data in conf_data.items():
                if not data["active"]:
                    continue

                module_name = data["module"]
                module_specs = find_spec(module_name)
                module = module_from_spec(module_specs)
                sys.modules[module_name] = module
                module_specs.loader.exec_module(module)
                self.notifiers[platform] = getattr(module, data["class"])()


    async def send(
        self, 
        platform, 
        receiver: str, 
        title: Translation, 
        body: Translation,
        image_urls: Translation
    ) -> bool:
        if platform not in self.notifiers:
            return False
        try:
            return await self.notifiers[platform].send(receiver, title, body, image_urls)
        except Exception as e:
            logger.info(
                "Notification",
                extra={
                    "props": {"title": f"FAIL at {self.notifiers[platform]}.send", "message": e}
                },
            )