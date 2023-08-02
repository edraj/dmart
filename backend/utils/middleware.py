from contextvars import ContextVar
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
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
            if k == 'cookie':
                continue
            request_headers[k] = v

        request_data = _request_data_ctx_var.set({
            "request_headers": request_headers,
        })

        await self.app(scope, receive, send)

        _request_data_ctx_var.reset(request_data)
