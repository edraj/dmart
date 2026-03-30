from firebase_admin import credentials, initialize_app, messaging  # type: ignore

from models.core import NotificationData
from utils.helpers import lang_code
from utils.notification import Notifier
from utils.settings import settings
from models.core import NotificationData
from data_adapters.adapter import data_adapter as db


class FirebaseNotifier(Notifier):
    def _init_connection(self) -> None:
        if not hasattr(self, "_firebase_app"):
            firebase_cred = credentials.Certificate(settings.google_application_credentials)
            self._firebase_app = initialize_app(firebase_cred, name="[DEFAULT]")

    async def send(self, data: NotificationData) -> bool:
        self._init_connection()
        # Prefer session firebase tokens (web + mobile); fallback to receiver.firebase_token
        receiver = data.receiver if isinstance(data.receiver, dict) else {}
        firebase_tokens: list[str] = list(receiver.get("firebase_tokens") or [])
        if not firebase_tokens and receiver.get("shortname"):
            firebase_tokens = await db.get_user_session_firebase_tokens(receiver["shortname"])
        if not firebase_tokens and receiver.get("firebase_token"):
            firebase_tokens = [receiver["firebase_token"]]
        if not firebase_tokens:
            raise Exception("Missing token for user shortname:"\
                f"{receiver.get('shortname')} - msisdn {receiver.get('msisdn')}")
        user_lang = lang_code(receiver.get("language", "ar"))
        title = data.title.__getattribute__(user_lang)
        body = data.body.__getattribute__(user_lang)
        image_url = (data.image_urls.__getattribute__(user_lang) if data.image_urls else "") or ""

        alert = messaging.ApsAlert(title=title, body=body)
        aps = messaging.Aps(alert=alert, sound="default", content_available=True)
        apns = messaging.APNSConfig(
            payload=messaging.APNSPayload(aps),
            fcm_options=messaging.APNSFCMOptions(image=image_url),
        )
        # apns = messaging.APNSConfig( payload = messaging.APNSPayload(aps))
        android_notification_settings = messaging.AndroidNotification(
            priority="high", channel_id="FCM_CHANNEL_ID", visibility="public", image=image_url
        )
        android_config = messaging.AndroidConfig(priority="high", notification=android_notification_settings)
        web_push = messaging.WebpushConfig(headers={"image": image_url})
        for fcm_token in firebase_tokens:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body), 
                token=fcm_token, 
                apns=apns, 
                android=android_config,
                webpush=web_push,
                data={**data.deep_link, "id": data.entry_id or ""}
            )
            messaging.send(message, app=self._firebase_app)
        return True
