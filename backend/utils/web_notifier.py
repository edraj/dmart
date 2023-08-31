from models.core import NotificationData
from utils.async_request import AsyncRequest
from utils.notification import Notifier
from utils.helpers import lang_code
from utils.settings import settings




class WebNotifier(Notifier):
    
    async def send(
        self, 
        data: NotificationData
    ):
        if not hasattr(self, "user") or self.user.shortname != data.receiver:
            await self._load_user(data.receiver)
        user_lang = lang_code(self.user.language)
        async with AsyncRequest() as client:
            await client.post(
                f"{settings.websocket_url}/send-message/{data.receiver}",
                json={
                    "title": data.title.__getattribute__(user_lang),
                    "description": data.body.__getattribute__(user_lang),
                }
            )

