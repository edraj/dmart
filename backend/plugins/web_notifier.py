import json
import requests
from models.core import Translation
from utils.notification import Notifier
from utils.helpers import lang_code
from utils.settings import settings




class WebNotifier(Notifier):
    
    async def send(
        self, 
        receiver: str, 
        title: Translation, 
        body: Translation, 
        image_urls: Translation | None = None
    ):
        if not hasattr(self, "user"):
            await self._load_user(receiver)
        user_lang = lang_code(self.user.language)
        requests.post(
            url=f"{settings.websocket_url}/send-message/{receiver}",
            data=json.dumps(
                {
                    "title": title.__getattribute__(user_lang),
                    "description": body.__getattribute__(user_lang),
                }
            ),
        )

