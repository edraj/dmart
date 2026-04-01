from typing import Any

from fastapi_sso.sso.base import DiscoveryDocument, OpenID, SSOBase
from fastapi_sso.sso.facebook import FacebookSSO
from fastapi_sso.sso.generic import create_provider
from fastapi_sso.sso.google import GoogleSSO
from httpx import AsyncClient

from utils.settings import settings

FACEBOOK_CLIENT_ID = settings.facebook_client_id
FACEBOOK_CLIENT_SECRET = settings.facebook_client_secret
FACEBOOK_OAUTH_CALLBACK = settings.facebook_oath_callback


def get_facebook_sso() -> FacebookSSO:
    return FacebookSSO(
        FACEBOOK_CLIENT_ID,
        FACEBOOK_CLIENT_SECRET,
        redirect_uri=FACEBOOK_OAUTH_CALLBACK,
    )


GOOGLE_CLIENT_ID = settings.google_client_id
GOOGLE_CLIENT_SECRET = settings.google_client_secret
GOOGLE_OAUTH_CALLBACK = settings.google_oath_callback


def get_google_sso() -> GoogleSSO:
    return GoogleSSO(
        GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, redirect_uri=GOOGLE_OAUTH_CALLBACK
    )


# Apple SSO
APPLE_CLIENT_ID = settings.apple_client_id  # Your Apple Services ID
APPLE_CLIENT_SECRET = settings.apple_client_secret
APPLE_OAUTH_CALLBACK = settings.apple_oath_callback


def apple_response_convertor(response: dict[str, Any], client: AsyncClient | None = None) -> OpenID:
    return OpenID(
        id=response.get("sub"),
        email=response.get("email"),
        first_name=response.get("fullName", []).split(" ")[0],
        last_name=response.get("fullName", []).split(" ")[-1],
        picture=response.get("picture"),
        provider="apple",
    )


def get_apple_sso() -> SSOBase:
    apple_discovery = DiscoveryDocument(
        {
            "authorization_endpoint": "https://appleid.apple.com/auth/authorize",
            "token_endpoint": "https://appleid.apple.com/auth/token",
            # "jwks_uri":"https://appleid.apple.com/auth/keys",
            "userinfo_endpoint": "https://appleid.apple.com/auth/userinfo",
        }
    )
    AppleProvider: type[SSOBase] = create_provider(
        name="apple",
        discovery_document=apple_discovery,
        default_scope=["fullName", "email"],
        response_convertor=apple_response_convertor,
    )

    return AppleProvider(
        client_id=APPLE_CLIENT_ID,
        client_secret=APPLE_CLIENT_SECRET,
        redirect_uri=APPLE_OAUTH_CALLBACK,
        allow_insecure_http=False,
    )
