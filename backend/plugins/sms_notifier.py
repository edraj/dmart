from api.user.service import send_sms
from models.core import Translation
from utils.helpers import lang_code
from utils.notification import Notifier


class SMSNotifier(Notifier):
    
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
        if not self.user.msisdn:
            return False
        await send_sms(
            self.user.msisdn, 
            title.__getattribute__(user_lang)
        )

