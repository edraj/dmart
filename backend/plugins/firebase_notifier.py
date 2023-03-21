from firebase_admin import credentials, messaging, initialize_app
from utils.notification import NotifierInterface
from utils.helpers import lang_code
from utils.settings import settings
from models.core import Translation

class FirebaseNotifier(NotifierInterface):
    
    def _init_connection(self) -> None:
        if not self._firebase_app:
            firebase_cred = credentials.Certificate(settings.google_application_credentials)
            self._firebase_app = initialize_app(firebase_cred, name="[DEFAULT]")



    async def send(
        self, 
        receiver: str, 
        title: Translation, 
        body: Translation, 
        image_urls: Translation | None = None
    ):
        self._init_connection()
        # Receiver should be user.firebase_token
        if not hasattr(self, "user"):
            await self._load_user(receiver)
        token = self.user.firebase_token
        user_lang = lang_code(self.user.language)
        title = title.__getattribute__(user_lang)
        body = body.__getattribute__(user_lang)
        image_url = image_urls.__getattribute__(user_lang)

        alert = messaging.ApsAlert(title = title, body = body)
        aps = messaging.Aps( alert = alert, sound = "default", content_available = True )
        apns = messaging.APNSConfig(
            payload=messaging.APNSPayload(aps),
            fcm_options=messaging.APNSFCMOptions(image=image_url),
        )
        # apns = messaging.APNSConfig( payload = messaging.APNSPayload(aps))
        android_notification_settings = messaging.AndroidNotification(
            priority="high", 
            channel_id="FCM_CHANNEL_ID", 
            visibility="public", 
            image=image_url
        )
        android_config = messaging.AndroidConfig(priority="high", notification=android_notification_settings)
        web_push = messaging.WebpushConfig(headers={"image": image_url})
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body), 
            token=token, 
            apns=apns, 
            android=android_config,
            webpush=web_push,
        )
        return messaging.send(message, app=self._firebase_app)

