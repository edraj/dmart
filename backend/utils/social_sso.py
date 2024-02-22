from fastapi_sso.sso.facebook import FacebookSSO
from fastapi_sso.sso.google import GoogleSSO
from utils.settings import settings

FACEBOOK_CLIENT_ID = settings.facebook_client_id
FACEBOOK_CLIENT_SECRET = settings.facebook_client_secret


def get_facebook_sso() -> FacebookSSO:
    return FacebookSSO(
        FACEBOOK_CLIENT_ID,
        FACEBOOK_CLIENT_SECRET,
        redirect_uri=f"{settings.app_url}/auth/facebook/callback",
    )


GOOGLE_CLIENT_ID = settings.google_client_id
GOOGLE_CLIENT_SECRET = settings.google_client_secret


def get_google_sso() -> GoogleSSO:
    return GoogleSSO(
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        redirect_uri=f"{settings.app_url}/auth/google/callback",
    )
