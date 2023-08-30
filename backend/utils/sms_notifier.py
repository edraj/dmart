from api.user.service import send_sms
from models.core import NotificationData
from utils.helpers import lang_code
from utils.notification import Notifier


class SMSNotifier(Notifier):
    
    async def send(
        self, 
        data: NotificationData
    ):
        if not hasattr(self, "user") or self.user.shortname != data.receiver:
            await self._load_user(data.receiver)
        user_lang = lang_code(self.user.language)
        if not self.user.msisdn:
            return False
        await send_sms(
            self.user.msisdn, 
            data.title.__getattribute__(user_lang)
        )

