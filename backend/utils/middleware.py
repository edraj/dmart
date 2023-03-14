from contextvars import ContextVar
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from typing import Optional
REQUEST_DATA_CTX_KEY = "request_data"

_request_data_ctx_var: ContextVar[dict] = ContextVar(REQUEST_DATA_CTX_KEY, default=Optional[dict])

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

        request_data = _request_data_ctx_var.set({
            "user_agent": request.headers.get("user-agent"),
            "id_address": request.headers.get("x-real-ip"),
        })

        await self.app(scope, receive, send)

        _request_data_ctx_var.reset(request_data)
