from api.user.service import send_sms
from models.core import NotificationData
from utils.helpers import lang_code
from utils.notification import Notifier


class SMSNotifier(Notifier):
    
    async def send(
        self, 
        data: NotificationData
    ) -> bool:
        user_lang = lang_code(data.receiver.get("language", "ar"))
        if "msisdn" not in data.receiver:
            return False
        await send_sms(
            data.receiver["msisdn"], 
            data.title.__getattribute__(user_lang)
        )
        return True

