from models.core import NotificationData
from utils.async_request import AsyncRequest
from utils.notification import Notifier
from utils.helpers import lang_code
from utils.settings import settings




class WebNotifier(Notifier):
    
    async def send(
        self, 
        data: NotificationData
    ) -> bool:
        if not settings.websocket_url:
            return False
        user_lang = lang_code(data.receiver.get("language", "ar"))
        async with AsyncRequest() as client:
            await client.post(
                f"{settings.websocket_url}/send-message/{data.receiver.get('shortname')}",
                json={
                    "title": data.title.__getattribute__(user_lang),
                    "description": data.body.__getattribute__(user_lang),
                }
            )
        
        return True

