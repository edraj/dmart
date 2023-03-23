import json
import requests
from models.core import NotificationData
from utils.notification import Notifier
from utils.helpers import lang_code
from utils.settings import settings




class WebNotifier(Notifier):
    
    async def send(
        self, 
        data: NotificationData
    ):
        if not hasattr(self, "user"):
            await self._load_user(data.receiver)
        user_lang = lang_code(self.user.language)
        requests.post(
            url=f"{settings.websocket_url}/send-message/{data.receiver}",
            data=json.dumps(
                {
                    "title": data.title.__getattribute__(user_lang),
                    "description": data.body.__getattribute__(user_lang),
                }
            ),
        )

