from contextvars import ContextVar
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
import models.api as api
from fastapi import status

REQUEST_DATA_CTX_KEY = "request_data"

_request_data_ctx_var: ContextVar[dict] = ContextVar(REQUEST_DATA_CTX_KEY, default={})

def get_request_data() -> dict:
    return _request_data_ctx_var.get()

class CustomRequestMiddleware:
    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ["http", "websocket"]:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_headers = {}
        for k,v in request.headers.items():
            if k in ['cookie', 'authorization']:
                continue
            request_headers[k] = v

        request_data = _request_data_ctx_var.set({
            "request_headers": request_headers,
        })

        await self.app(scope, receive, send)

        _request_data_ctx_var.reset(request_data)


class ChannelMiddleware:
    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ["http", "websocket"] or not settings.enable_channel_auth:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        channel_key = request.headers.get("x-channel-key")
        if not channel_key:
            raise api.Exception(
                status_code=status.HTTP_403_FORBIDDEN,
                error=api.Error(
                    type="channel_auth", code=InternalErrorCode.NOT_ALLOWED, message="Requested method or path is forbidden"
                ),
            )
        
        request_channel_name: str | None = None
        for channel, config in settings.channels:
            if channel_key in config.get("keys", []):
                request_channel_name = channel
                break
            
        if not request_channel_name:
            raise api.Exception(
                status_code=status.HTTP_403_FORBIDDEN,
                error=api.Error(
                    type="channel_auth", code=InternalErrorCode.NOT_ALLOWED, message="Requested method or path is forbidden [2]"
                ),
            )
            
        for pattern in settings.channels[request_channel_name]["allowed_api_patterns"]:
            if pattern.search(request.scope['path']):
                await self.app(scope, receive, send)
                return
            
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(
                type="channel_auth", code=InternalErrorCode.NOT_ALLOWED, message="Requested method or path is forbidden [3]"
            ),
        )
                
            
        
        print(request.scope['path'])
            
