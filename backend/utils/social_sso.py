from time import time
from typing import Any, Optional
from fastapi import HTTPException
from fastapi_sso.sso.facebook import FacebookSSO
from fastapi_sso.sso.google import GoogleSSO
from httpx import AsyncClient
from utils.settings import settings
from fastapi_sso.sso.generic import create_provider
from fastapi_sso.sso.base import OpenID, SSOBase
from jwt import encode


FACEBOOK_CLIENT_ID = settings.facebook_client_id
FACEBOOK_CLIENT_SECRET = settings.facebook_client_secret


def get_facebook_sso() -> FacebookSSO:
    return FacebookSSO(
        FACEBOOK_CLIENT_ID,
        FACEBOOK_CLIENT_SECRET,
        redirect_uri=f"{settings.app_url}/user/facebook/callback",
    )


GOOGLE_CLIENT_ID = settings.google_client_id
GOOGLE_CLIENT_SECRET = settings.google_client_secret


def get_google_sso() -> GoogleSSO:
    return GoogleSSO(
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        redirect_uri=f"{settings.app_url}/user/google/callback",
    )

# Apple SSO
APPLE_PRIVATE_KEY_PATH = "path/to/AuthKey_XXXXXXXXXX.p8" # Path to your Apple private key file (.p8)
APPLE_CLIENT_ID = settings.apple_client_id # Your Apple Services ID 
APPLE_KEY_ID = "YOUR_KEY_ID"  # From Apple Developer Portal
APPLE_CLIENT_SECRET = settings.apple_client_secret
APPLE_TEAM_ID = "YOUR_TEAM_ID"  # From Apple Developer Portal
def get_apple_private_key():
    try:
        with open(APPLE_PRIVATE_KEY_PATH, 'r') as key_file:
            return key_file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Apple private key file not found")
    
def generate_client_secret():
    private_key = get_apple_private_key()
    now = int(time())
    payload = {
        "iss": APPLE_TEAM_ID,
        "iat": now,
        "exp": now + 86400 * 180,  # Valid for 6 months
        "aud": "https://appleid.apple.com",
        "sub": APPLE_CLIENT_ID
    }
    headers = {
        "kid": APPLE_KEY_ID,
        "alg": "ES256"
    }
    try:
        client_secret = encode(
            payload,
            private_key,
            algorithm="ES256",
            headers=headers
        )
        return client_secret
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate client secret: {str(e)}")
    
def apple_response_convertor(response: dict[str, Any], client: Optional[AsyncClient] = None) -> OpenID:
    print(f"==>> response: {response}")
    return OpenID()
    
    
def get_apple_sso() -> SSOBase:
    apple_discovery = {
        "authorization_endpoint":"https://appleid.apple.com/auth/authorize",
        "token_endpoint":"https://appleid.apple.com/auth/token",
        "jwks_uri":"https://appleid.apple.com/auth/keys",
        "userinfo_endpoint": "http://localhost:9090/me",
        
    }
    AppleProvider: type[SSOBase] = create_provider(
        name="apple", 
        discovery_document=apple_discovery,
        default_scope=["name", "email"],
        response_convertor=apple_response_convertor
    )
    
    return AppleProvider(
        client_id=APPLE_CLIENT_ID,
        client_secret=APPLE_CLIENT_SECRET,
        redirect_uri=f"{settings.app_url}/user/apple/callback",
        allow_insecure_http=True
    )