import jwt
from time import time
from typing import Optional, Any
from fastapi import Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from utils.settings import settings
from utils.redis_services import RedisServices
import models.api as api


def decode_jwt(token: str) -> dict[str, Any]:
    decoded_token: dict
    try:
        decoded_token = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except Exception:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=27, message="Invalid Token [1]"),
        )
    if (
        not decoded_token
        or "data" not in decoded_token
        or "expires" not in decoded_token
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=27, message="Invalid Token [2]"),
        )
    if decoded_token["expires"] <= time():
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=28, message="Expired Token"),
        )

    if isinstance(decoded_token["data"], dict):
        return decoded_token["data"]
    else:
        return {}


class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> str | None:  # type: ignore
        user_shortname: str | None = None
        try:
            # Handle token received in Auth header
            credentials: Optional[HTTPAuthorizationCredentials] = await super(
                JWTBearer, self
            ).__call__(request)
            if credentials and credentials.scheme == "Bearer":
                decoded = decode_jwt(credentials.credentials)
                if decoded and "username" in decoded:
                    user_shortname = decoded["username"]
        except Exception:
            # Handle token received in the cookie
            auth_token = request.cookies.get("auth_token")
            if auth_token:
                decoded = decode_jwt(auth_token)
                if decoded and "username" in decoded and decoded["username"]:
                    user_shortname = decoded["username"]
        finally:
            if not user_shortname:
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(type="jwtauth", code=13,
                              message="Not authenticated [1]"),
                )

            async with RedisServices() as redis:
                user_redis_session = await redis.get(
                    f"user_login_session:{user_shortname}"
                )
                if not user_redis_session:
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="jwtauth", code=13, message="Not authenticated [2]"
                        ),
                    )
                # Update the session with a new TTL
                await redis.set(
                    key=f"user_login_session:{user_shortname}",
                    value=1,
                    ex=settings.session_inactivity_ttl,
                )
            return user_shortname


class GetJWTToken(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(GetJWTToken, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> str | None:  # type: ignore
        try:
            credentials: Optional[HTTPAuthorizationCredentials] = await super(
                GetJWTToken, self
            ).__call__(request)
            if credentials and credentials.scheme == "Bearer":
                return credentials.credentials
        except Exception:
            return request.cookies.get("auth_token")
        return None


def sign_jwt(data: dict, expires: int = 86400) -> str:
    payload = {"data": data, "expires": time() + expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def set_redis_session_key(user_shortname: str) -> bool:
    async with RedisServices() as redis:
        return bool(await redis.set(
            key=f"user_login_session:{user_shortname}",
            value=1,
            ex=settings.session_inactivity_ttl,
        ))


async def remove_redis_session_key(user_shortname: str) -> bool:
    async with RedisServices() as redis:
        return bool(
            await redis.del_keys([f"user_login_session:{user_shortname}"])
        )


# if __name__ == "__main__":
    # import os
    # mport binascii

    # Generate secret
    # print(binascii.hexlify(os.urandom(24)))
#    pass
