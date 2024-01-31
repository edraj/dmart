import jwt
from time import time
from typing import Optional, Any
from fastapi import Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from utils.internal_error_code import InternalErrorCode

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
            api.Error(type="jwtauth", code=InternalErrorCode.INVALID_TOKEN, message="Invalid Token [1]"),
        )
    if (
        not decoded_token
        or "data" not in decoded_token
        or "expires" not in decoded_token
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=InternalErrorCode.INVALID_TOKEN, message="Invalid Token [2]"),
        )
    if decoded_token["expires"] <= time():
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=InternalErrorCode.EXPIRED_TOKEN, message="Expired Token"),
        )
        

    if isinstance(decoded_token["data"], dict) and decoded_token["data"].get("username"):
        return decoded_token["data"]
    else:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=InternalErrorCode.INVALID_TOKEN, message="Invalid Token [3]"),
        )


class JWTBearer(HTTPBearer):
    is_required: bool = True

    def __init__(self, auto_error: bool = True, is_required: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)
        self.is_required = is_required

    async def __call__(self, request: Request) -> str | None:  # type: ignore
        user_shortname : str | None = None
        auth_token : str | None = None
        try:
            # Handle token received in Auth header
            credentials: Optional[HTTPAuthorizationCredentials] = await super(
                JWTBearer, self
            ).__call__(request)
            if credentials and credentials.scheme == "Bearer":
                auth_token = credentials.credentials
                
        except Exception:
            # Handle token received in the cookie
            auth_token = request.cookies.get("auth_token")
            
        if not auth_token:
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(type="jwtauth", code=InternalErrorCode.NOT_AUTHENTICATED, message="Not authenticated [1]"),
            )
            
        decoded = decode_jwt(auth_token)
        user_shortname = decoded["username"]
        
        active_session_token = await get_redis_active_session(user_shortname)
        if active_session_token != auth_token:
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="jwtauth", code=InternalErrorCode.NOT_AUTHENTICATED, message="Not authenticated [2]"
                ),
            )
            
        await set_redis_active_session(user_shortname, active_session_token)
        
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

def generate_jwt(data: dict, expires: int = 86400) -> str:
    payload = {"data": data, "expires": time() + expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

async def sign_jwt(data: dict, expires: int = 86400) -> str:
    token = generate_jwt(data, expires)
    await set_redis_active_session(data["username"], token)
    return token


async def set_redis_active_session(user_shortname: str, token: str) -> bool:
    async with RedisServices() as redis:
        return bool(await redis.set(
            key=f"active_session:{user_shortname}",
            value=token,
            ex=settings.session_inactivity_ttl,
        ))
        
async def get_redis_active_session(user_shortname: str) -> str | None:
    async with RedisServices() as redis:
        return await redis.get(
            f"active_session:{user_shortname}"
        )


async def remove_redis_active_session(user_shortname: str) -> bool:
    async with RedisServices() as redis:
        return bool(
            await redis.del_keys([f"active_session:{user_shortname}"])
        )


# if __name__ == "__main__":
    # import os
    # mport binascii

    # Generate secret
    # print(binascii.hexlify(os.urandom(24)))
#    pass
