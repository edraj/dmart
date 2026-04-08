#!/usr/bin/env -S BACKEND_ENV=config.env python3
"""Main module"""

import asyncio
import json
import os
import socket
import sys
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from os import getpid
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.logger import logger
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from hypercorn.asyncio import serve
from hypercorn.config import Config
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import ValidationError
from starlette.concurrency import iterate_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

import models.api as api
from api.info.router import git_info
from api.info.router import router as info
from api.managed.router import router as managed
from api.public.router import router as public
from api.qr.router import router as qr
from api.user.router import router as user
from data_adapters.adapter import data_adapter as db
from languages.loader import load_langs
from utils.internal_error_code import InternalErrorCode
from utils.jwt import decode_jwt
from utils.logger import logging_schema
from utils.middleware import ChannelMiddleware, CustomRequestMiddleware
from utils.plugin_manager import plugin_manager
from utils.settings import settings


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404 and path != "index.html" and not os.path.splitext(path)[1]:
                try:
                    return await super().get_response("index.html", scope)
                except StarletteHTTPException:
                    pass
            raise ex


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up")
    print('{"stage":"starting up"}')

    openapi_schema = app.openapi()
    paths = openapi_schema["paths"]
    for path in paths:
        for method in paths[path]:
            responses = paths[path][method]["responses"]
            if responses.get("422"):
                responses.pop("422")
    app.openapi_schema = openapi_schema

    await db.initialize_spaces()
    # await plugin_manager.load_plugins(app, capture_body)
    yield

    logger.info("Application shutting down")
    print('{"stage":"shutting down"}')
    if hasattr(db, "engine"):
        await db.engine.dispose()  # type: ignore[attr-defined]


app = FastAPI(
    lifespan=lifespan,
    title="Datamart API",
    description="Structured Content Management System",
    version=str(git_info["tag"]),
    redoc_url=None,
    docs_url=f"{settings.base_path}/docs",
    openapi_url=f"{settings.base_path}/openapi.json",
    servers=[{"url": f"{settings.base_path}/"}],
    contact={
        "name": "Kefah T. Issa",
        "url": "https://dmart.cc",
        "email": "kefah.issa@gmail.com",
    },
    license_info={
        "name": "GNU Affero General Public License v3+",
        "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
    },
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    openapi_tags=[
        {"name": "user", "description": "User registration, login, profile and delete"},
        {
            "name": "managed",
            "description": "Login-only content management api and media upload",
        },
        {
            "name": "public",
            "description": "Public api for query and GET access to media",
        },
    ],
    default_response_class=JSONResponse,
)


async def capture_body(request: Request):
    """Capture request body metadata for logging. Captures JSON bodies
    directly and lightweight metadata for multipart uploads."""
    request.state.request_body = {}

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.body()
            if body:
                request.state.request_body = json.loads(body)
        except Exception:
            pass
        return

    if request.method != "POST":
        return

    if "multipart/form-data" in content_type:
        form = await request.form()
        for field in form:
            one = form[field]
            if isinstance(one, str):
                request.state.request_body[field] = form.get(field)
            elif isinstance(one, UploadFile):
                request.state.request_body[field] = {
                    "name": one.filename,
                    "content_type": one.content_type,
                }


@app.exception_handler(StarletteHTTPException)
async def my_exception_handler(_, exception):
    return JSONResponse(content=exception.detail, status_code=exception.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    err = jsonable_encoder({"detail": exc.errors()})["detail"]
    raise api.Exception(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        error=api.Error(
            code=InternalErrorCode.UNPROCESSABLE_ENTITY, type="validation", message="Validation error [1]", info=err
        ),
    )


app.add_middleware(CustomRequestMiddleware)
app.add_middleware(ChannelMiddleware)


def set_middleware_extra(request, response, start_time, user_shortname, exception_data, response_body):
    extra = {
        "props": {
            "timestamp": start_time,
            "duration": 1000 * (time.time() - start_time),
            "server": socket.gethostname(),
            "process_id": getpid(),
            "user_shortname": user_shortname,
            "request": {
                "url": request.url._url,
                "verb": request.method,
                "path": quote(str(request.url.path)),
                "query_params": dict(request.query_params.items()),
                "headers": dict(request.headers.items()),
            },
            "response": {
                "headers": dict(response.headers.items()),
                "http_status": response.status_code,
            },
        }
    }

    if exception_data is not None:
        extra["props"]["exception"] = exception_data

    if hasattr(request.state, "request_body"):
        extra["props"]["request"]["body"] = request.state.request_body

    if response_body and isinstance(response_body, dict):
        extra["props"]["response"]["body"] = response_body

    return extra


def set_middleware_response_headers(request, response):
    request_origin = request.headers.get("origin", "")

    if settings.allowed_cors_origins:
        if request_origin in settings.allowed_cors_origins:
            response.headers["Access-Control-Allow-Origin"] = request_origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        # If origin not in allowlist, do not set CORS headers (browser will block)
    else:
        # Fallback: allow same-host origin only (no open reflection)
        default_origin = f"http://{settings.listening_host}:{settings.listening_port}"
        response.headers["Access-Control-Allow-Origin"] = request_origin if request_origin == default_origin else default_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"

    response.headers["Access-Control-Allow-Headers"] = "content-type, charset, authorization, accept-language, content-length"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Access-Control-Allow-Methods"] = "OPTIONS, DELETE, POST, GET, PATCH, PUT"

    # Only set no-cache for API responses; static files should be cacheable
    request_path = request.url.path
    if request_path.startswith(settings.cxb_url) or request_path.endswith((".js", ".css", ".png", ".svg", ".ico", ".woff2")):
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["x-server-time"] = datetime.now().isoformat()
    response.headers["Access-Control-Expose-Headers"] = "x-server-time"

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


_SENSITIVE_KEYS = frozenset({"password", "access_token", "refresh_token", "auth_token", "jwt", "otp", "code", "token"})


def mask_sensitive_data(data, _depth: int = 0):
    """Mask sensitive keys in dicts/lists. Stops recursing beyond depth 4
    to avoid deep-walking large query result payloads."""
    if _depth > 4:
        return data
    if isinstance(data, dict):
        return {k: "******" if k in _SENSITIVE_KEYS else mask_sensitive_data(v, _depth + 1) for k, v in data.items()}
    elif isinstance(data, list):
        # Only recurse into short lists to avoid walking thousands of records
        if len(data) > 20:
            return data
        return [mask_sensitive_data(item, _depth + 1) for item in data]
    elif isinstance(data, str) and "auth_token" in data:
        return "******"
    return data


def set_logging(response, extra, request, exception_data):
    _extra = mask_sensitive_data(extra)
    if isinstance(_extra, dict):
        if 400 <= response.status_code < 500:
            logger.warning("Served request", extra=_extra)
        elif response.status_code >= 500 or exception_data is not None:
            logger.error("Served request", extra=_extra)
        elif request.method != "OPTIONS" and not request.url.path.startswith(
            settings.cxb_url
        ):  # Do not log OPTIONS request, to reduce excessive logging
            logger.info("Served request", extra=_extra)


def set_stack(e):
    return [
        {
            "file": frame.f_code.co_filename,
            "function": frame.f_code.co_name,
            "line": lineno,
        }
        for frame, lineno in traceback.walk_tb(e.__traceback__)
        if "site-packages" not in frame.f_code.co_filename
    ]


@app.middleware("http")
async def middle(request: Request, call_next):
    """Wrapper function to manage errors and logging"""
    if (
        request.url._url.endswith("/docs")
        or request.url._url.endswith("openapi.json")
        or request.url._url.endswith("/favicon.ico")
    ):
        return await call_next(request)

    start_time = time.time()
    response_body: str | dict = {}
    exception_data: dict[str, Any] | None = None

    try:
        response = await asyncio.wait_for(call_next(request), timeout=settings.request_timeout)
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            raw_response = [section async for section in response.body_iterator]
            response.body_iterator = iterate_in_threadpool(iter(raw_response))
            raw_data = b"".join(raw_response)
            if raw_data:
                try:
                    response_body = json.loads(raw_data)
                except Exception:
                    response_body = {}
    except TimeoutError:
        response_body = {"status": "failed", "error": {"code": 504, "message": "Request processing time excedeed limit"}}
        response = JSONResponse(content=response_body, status_code=status.HTTP_504_GATEWAY_TIMEOUT)
    except api.Exception as e:
        if e.error.message.startswith("(sqlalchemy.dialects.postgresql"):
            response_body = {"status": "failed", "error": "Something went wrong"}
            response = JSONResponse(status_code=500, content=response_body)
        else:
            response_body = jsonable_encoder(api.Response(status=api.Status.failed, error=e.error))
            response = JSONResponse(status_code=e.status_code, content=response_body)
        stack = set_stack(e)
        exception_data = {"props": {"exception": str(e), "stack": stack}}
    except ValidationError as e:
        stack = set_stack(e)
        exception_data = {"props": {"exception": str(e), "stack": stack}}
        response_body = {
            "status": "failed",
            "error": {
                "type": "validation",
                "code": 422,
                "message": "Validation error [2]",
                "info": jsonable_encoder(e.errors()),
            },
        }
        response = JSONResponse(status_code=422, content=response_body)
    except SchemaValidationError as e:
        stack = set_stack(e)
        exception_data = {"props": {"exception": str(e), "stack": stack}}
        response_body = {
            "status": "failed",
            "error": {
                "type": "validation",
                "code": 422,
                "message": "Validation error [3]",
                "info": [{"loc": list(e.path), "msg": e.message}],
            },
        }
        response = JSONResponse(status_code=400, content=response_body)
    except Exception:
        exception_message = ""
        stack = None
        if ee := sys.exc_info()[1]:
            stack = set_stack(ee)
            exception_message = str(ee)
            exception_data = {"props": {"exception": str(ee), "stack": stack}}

        error_log: dict[str, Any] = {"type": "general", "code": 99, "message": exception_message}
        if settings.debug_enabled:
            error_log["stack"] = stack
        response_body = {"status": "failed", "error": error_log}
        response = JSONResponse(status_code=500, content=response_body)

    response = set_middleware_response_headers(request, response)

    # Extract user_shortname for logging without re-decoding the JWT.
    # For login requests, use the request body; for other requests, use
    # a lightweight cookie/header peek instead of full JWTBearer validation.
    user_shortname = "guest"
    if request.url.path == "/user/login":
        try:
            body = getattr(request.state, "request_body", {}) or {}
            if isinstance(body, dict):
                shortname_value = body.get("shortname")
                if isinstance(shortname_value, str) and shortname_value.strip():
                    user_shortname = shortname_value
        except Exception:
            pass
    else:
        try:
            auth_header = request.headers.get("authorization", "")
            auth_token = auth_header[7:] if auth_header.startswith("Bearer ") else request.cookies.get("auth_token")
            if auth_token:
                decoded = decode_jwt(auth_token)
                user_shortname = decoded.get("shortname", "guest")
        except Exception:
            user_shortname = "guest"

    extra = set_middleware_extra(request, response, start_time, user_shortname, exception_data, response_body)

    set_logging(response, extra, request, exception_data)

    if settings.hide_stack_trace and (
        response_body
        and isinstance(response_body, dict)
        and "error" in response_body
        and isinstance(response_body["error"], dict)
        and "stack" in response_body["error"]
    ):
        response_body["error"].pop("stack", None)
        response = JSONResponse(
            status_code=response.status_code,
            content=response_body,
            headers=dict(response.headers),
        )

    return response


app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Correlation-ID",
    update_request_header=False,
    validator=None,
)

app.add_middleware(GZipMiddleware, minimum_size=10000)


@app.get("/", include_in_schema=False)
async def root():
    """Dummy api end point"""
    return {"status": "success", "message": "DMART API"}


# @app.get("/s", include_in_schema=False)
# async def secrets(key):
#    if key == "alpha":
#        return settings.dict()

"""
@app.get("/spaces-backup", include_in_schema=False)
async def space_backup(key: str):
    if not key or key != "ABC":
        return api.Response(
            status=api.Status.failed,
            error=api.Error(type="git", code=InternalErrorCode.INVALID_APP_KEY, message="Api key is invalid"),
        )

    import subprocess

    cmd = "/usr/bin/bash -c 'cd .. && ./spaces-backup.sh'"
    # cmd = "../git-update.sh"

    result_stdout, result_stderr = subprocess.Popen(
        cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).communicate()
    attributes = {
        "stdout": result_stdout.decode().split("\n"),
        "stderr": result_stderr.decode().split("\n"),
    }
    return api.Response(status=api.Status.success, attributes=attributes)
"""

app.include_router(user, prefix="/user", tags=["user"], dependencies=[Depends(capture_body)])
app.include_router(managed, prefix="/managed", tags=["managed"], dependencies=[Depends(capture_body)])
app.include_router(
    qr,
    prefix="/qr",
    tags=["QR"],
    dependencies=[Depends(capture_body)],
)

app.include_router(public, prefix="/public", tags=["public"], dependencies=[Depends(capture_body)])

app.include_router(info, prefix="/info", tags=["info"], dependencies=[Depends(capture_body)])

# Load plugins: use existing event loop if available, otherwise create one
_background_plugin_tasks: set[asyncio.Task] = set()  # prevent GC of tasks
try:
    _loop = asyncio.get_running_loop()
    _t = _loop.create_task(plugin_manager.load_plugins(app, capture_body))
    _background_plugin_tasks.add(_t)
    _t.add_done_callback(_background_plugin_tasks.discard)
except RuntimeError:
    asyncio.run(plugin_manager.load_plugins(app, capture_body))


cxb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cxb")
if os.path.isdir(os.path.join(cxb_path, "client")):
    cxb_path = os.path.join(cxb_path, "client")

if not os.path.exists(os.path.join(cxb_path, "index.html")):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cxb_dist_path = os.path.join(project_root, "cxb", "dist", "client")
    if os.path.isdir(cxb_dist_path):
        cxb_path = cxb_dist_path

if os.path.isdir(cxb_path):

    @app.get(f"{settings.cxb_url}/config.json", include_in_schema=False)
    async def get_cxb_config():
        if settings.cxb_config_path and os.path.exists(settings.cxb_config_path):  # noqa: ASYNC240
            return FileResponse(settings.cxb_config_path)

        if os.path.exists("config.json"):  # noqa: ASYNC240
            return FileResponse("config.json")

        user_config = settings.spaces_folder / "config.json"
        if user_config.exists():
            return FileResponse(user_config)

        home_config = Path.home() / ".dmart" / "config.json"
        if home_config.exists():
            return FileResponse(home_config)

        bundled_config = os.path.join(cxb_path, "config.json")
        if os.path.exists(bundled_config):  # noqa: ASYNC240
            return FileResponse(bundled_config)

        return {
            "title": "DMART Unified Data Platform",
            "footer": "dmart.cc unified data platform",
            "short_name": "dmart",
            "display_name": "dmart",
            "description": "dmart unified data platform",
            "default_language": "en",
            "languages": {"ar": "العربية", "en": "English"},
            "backend": f"{settings.app_url}"
            if settings.app_url
            else f"http://{settings.listening_host}:{settings.listening_port}",
            "websocket": settings.websocket_url
            if settings.websocket_url
            else f"ws://{settings.listening_host}:{settings.websocket_port}/ws",
            "cxb_url": settings.cxb_url,
        }

    app.mount(settings.cxb_url, SPAStaticFiles(directory=cxb_path, html=True), name="cxb")


@app.options("/{x:path}", include_in_schema=False)
async def myoptions():
    return Response(status_code=status.HTTP_200_OK)


@app.get("/{x:path}", include_in_schema=False)
@app.post("/{x:path}", include_in_schema=False)
@app.put("/{x:path}", include_in_schema=False)
@app.patch("/{x:path}", include_in_schema=False)
@app.delete("/{x:path}", include_in_schema=False)
async def catchall(x):
    if x.startswith(settings.cxb_url.strip("/")):
        return RedirectResponse(f"{settings.cxb_url}/")
    raise api.Exception(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        error=api.Error(type="catchall", code=InternalErrorCode.INVALID_ROUTE, message="Requested method or path is invalid"),
    )


load_langs()


async def main():
    config = Config()
    config.bind = [f"{settings.listening_host}:{settings.listening_port}"]
    config.backlog = 2000

    config.logconfig_dict = logging_schema
    config.errorlog = logger

    try:
        await serve(cast(Any, app), config)
    except OSError as e:
        print("[!1server]", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("[!1server]", e)
