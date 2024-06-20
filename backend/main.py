#!/usr/bin/env -S BACKEND_ENV=config.env python3
""" Main module """
# from logging import handlers
from starlette.datastructures import UploadFile
from contextlib import asynccontextmanager
import asyncio
import json
from os import getpid
import sys
import time
import traceback
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, quote
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import  ValidationError
from languages.loader import load_langs
from utils.middleware import CustomRequestMiddleware
from utils.jwt import JWTBearer
from utils.plugin_manager import plugin_manager
from utils.redis_services import RedisServices
from utils.spaces import initialize_spaces
from fastapi import Depends, FastAPI, Request, Response, status
from utils.logger import logging_schema
from fastapi.logger import logger
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from utils.access_control import access_control
from fastapi.responses import JSONResponse
from hypercorn.asyncio import serve
from hypercorn.config import Config
from starlette.concurrency import iterate_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
import models.api as api
from utils.settings import settings
from asgi_correlation_id import CorrelationIdMiddleware

from api.managed.router import router as managed
from api.qr.router import router as qr
from api.public.router import router as public
from api.user.router import router as user
from api.info.router import router as info

from utils.internal_error_code import InternalErrorCode

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up")
    print('{"stage":"starting up"}')
    # , extra={"props":{
    #    "bind_address": f"{settings.listening_host}:{settings.listening_port}",
    #    "redis_port": settings.redis_port
    #    }})

    openapi_schema = app.openapi()
    paths = openapi_schema["paths"]
    for path in paths:
        for method in paths[path]:
            responses = paths[path][method]["responses"]
            if responses.get("422"):
                responses.pop("422")
    app.openapi_schema = openapi_schema

    await initialize_spaces()
    await access_control.load_permissions_and_roles()

    yield
    
    await RedisServices.POOL.aclose()
    await RedisServices.POOL.disconnect(True)
    
    logger.info("Application shutting down")
    print('{"stage":"shutting down"}')



app = FastAPI(
    lifespan=lifespan,
    title="Datamart API",
    description="Structured Content Management System",
    version="1.1.0",
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
)


async def capture_body(request: Request):
    request.state.request_body = {}

    if (
        request.method == "POST"
        and "application/json" in request.headers.get("content-type", "")
    ):
        request.state.request_body = await request.json()

    if (
        request.method == "POST"
        and request.headers.get("content-type")
        and "multipart/form-data" in request.headers.get("content-type", [])
    ):
        form = await request.form()
        for field in form:
            one = form[field]
            if isinstance(one, str):
                request.state.request_body[field] = form.get(field)
            elif isinstance(one, UploadFile):
                # TODO try to find a way to capture .json file content without await exeption
                # inner_json= form.get(field).file
                # form_to_dict[field]["file_name"]=form.get(field).filename
                # form_to_dict[field]["content_type"]=form.get(field).content_type
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
    # print(exc)
    raise api.Exception(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error=api.Error(
            code=InternalErrorCode.UNPROCESSABLE_ENTITY, type="validation", message="Validation error [1]", info=err
        ),
    )


app.add_middleware(CustomRequestMiddleware)

@app.middleware("http")
async def middle(request: Request, call_next):
    """Wrapper function to manage errors and logging"""
    # print(f"\n\n _available_connections: {len(RedisServices.POOL._available_connections)}\n_in_use_connections: {len(RedisServices._RedisServices__POOL._in_use_connections)}\n\n")
    if request.url._url.endswith("/docs") or request.url._url.endswith("openapi.json"):
        return await call_next(request)

    start_time = time.time()
    response_body: str | dict = {}
    exception_data: dict[str, Any] | None = None
    try:
        response = await call_next(request)
        raw_response = [section async for section in response.body_iterator]
        response.body_iterator = iterate_in_threadpool(iter(raw_response))
        raw_data = b"".join(raw_response)
        if raw_data:
            try:
                response_body = json.loads(raw_data)
            except Exception:
                response_body = {}
    except api.Exception as e:
        response = JSONResponse(
            status_code=e.status_code,
            content=jsonable_encoder(
                api.Response(status=api.Status.failed, error=e.error)
            ),
        )
        stack = [
            {
                "file": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "line": lineno,
            }
            for frame, lineno in traceback.walk_tb(e.__traceback__)
            if "site-packages" not in frame.f_code.co_filename
        ]
        exception_data = {"props": {"exception": str(e), "stack": stack}}
        response_body = json.loads(response.body.decode())
    except ValidationError as e:
        stack = [
            {
                "file": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "line": lineno,
            }
            for frame, lineno in traceback.walk_tb(e.__traceback__)
            if "site-packages" not in frame.f_code.co_filename
        ]
        exception_data = {"props": {"exception": str(e), "stack": stack}}
        response = JSONResponse(
            status_code=422,
            content={
                "status": "failed",
                "error": {
                    "code": 422,
                    "message": "Validation error [2]",
                    "info": e.errors(),
                },
            },
        )
        response_body = json.loads(response.body.decode())
    except SchemaValidationError as e:
        stack = [
            {
                "file": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "line": lineno,
            }
            for frame, lineno in traceback.walk_tb(e.__traceback__)
            if "site-packages" not in frame.f_code.co_filename
        ]
        exception_data = {"props": {"exception": str(e), "stack": stack}}
        response = JSONResponse(
            status_code=400,
            content={
                "status": "failed",
                "error": {
                    "code": 422,
                    "message": "Validation error [3]",
                    "info": [{
                        "loc": list(e.path),
                        "msg": e.message
                    }],
                },
            },
        )
        response_body = json.loads(response.body.decode())
    except Exception:
        exception_message = ""
        stack = None
        if ee := sys.exc_info()[1]:
            stack = [
                {
                    "file": frame.f_code.co_filename,
                    "function": frame.f_code.co_name,
                    "line": lineno,
                }
                for frame, lineno in traceback.walk_tb(ee.__traceback__)
                if "site-packages" not in frame.f_code.co_filename
            ]
            exception_message = str(ee)
            exception_data = {"props": {"exception": str(ee), "stack": stack}}

        error_log = {"code": 99, "message": exception_message}
        if settings.debug_enabled:
            error_log["stack"] = stack
        response = JSONResponse(
            status_code=500,
            content={
                "status": "failed",
                "error": error_log,
            },
        )
        response_body = json.loads(response.body.decode())

    referer = request.headers.get(
        "referer",
        request.headers.get("origin",
        request.headers.get("x-forwarded-proto", "http")
        + "://"
        + request.headers.get(
            "x-forwarded-host", f"{settings.listening_host}:{settings.listening_port}"
        )),
    )
    origin = urlparse(referer)
    response.headers[
        "Access-Control-Allow-Origin"
    ] = f"{origin.scheme}://{origin.netloc}"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "content-type, charset"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers[
        "Access-Control-Allow-Methods"
    ] = "OPTIONS, DELETE, POST, GET, PATCH, PUT"

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["x-server-time"] = datetime.now().isoformat()
    response.headers["Access-Control-Expose-Headers"] = "x-server-time"

    user_shortname = "guest"
    try:
        user_shortname = str(await JWTBearer().__call__(request))
    except Exception:
        pass

    extra = {
        "props": {
            "timestamp": start_time,
            "duration": 1000 * (time.time() - start_time),
            "server": settings.servername,
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
    if (hasattr(request.state, "request_body") and isinstance(extra, dict) and isinstance(extra["props"], dict) 
        and isinstance(extra["props"]["request"], dict)):
        extra["props"]["request"]["body"] = request.state.request_body
    if (response_body and isinstance(extra, dict) and isinstance(extra["props"], dict) 
        and isinstance(extra["props"]["response"], dict)):
        extra["props"]["response"]["body"] = response_body

    if response.status_code >= 400 and response.status_code < 500:
        logger.warning("Served request", extra=extra)
    elif response.status_code >= 500 or exception_data is not None:
        logger.error("Served request", extra=extra)
    elif request.method != "OPTIONS":  # Do not log OPTIONS request, to reduce excessive logging
        logger.info("Served request", extra=extra)

    return response


app.add_middleware(
    CorrelationIdMiddleware,
    header_name='X-Correlation-ID',
    update_request_header=False,
)
@app.get("/", include_in_schema=False)
async def root():
    """Dummy api end point"""
    return {"status": "success", "message": "DMART API"}


# @app.get("/s", include_in_schema=False)
# async def secrets(key):
#    if key == "alpha":
#        return settings.dict()


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
        "stdout": result_stdout.split("\n"),
        "stderr": result_stderr.split("\n"),
    }
    return api.Response(status=api.Status.success, attributes=attributes)


app.include_router(
    user, prefix="/user", tags=["user"], dependencies=[Depends(capture_body)]
)
app.include_router(
    managed, prefix="/managed", tags=["managed"], dependencies=[Depends(capture_body)]
)
app.include_router(
    qr,
    prefix="/qr",
    tags=["QR"],
    dependencies=[Depends(capture_body)],
)

app.include_router(
    public, prefix="/public", tags=["public"], dependencies=[Depends(capture_body)]
)

app.include_router(
    info, prefix="/info", tags=["info"], dependencies=[Depends(capture_body)]
)
# load plugins
asyncio.run(plugin_manager.load_plugins(app, capture_body))


@app.options("/{x:path}", include_in_schema=False)
async def myoptions():
    return Response(status_code=status.HTTP_200_OK)


@app.get("/{x:path}", include_in_schema=False)
@app.post("/{x:path}", include_in_schema=False)
@app.put("/{x:path}", include_in_schema=False)
@app.patch("/{x:path}", include_in_schema=False)
@app.delete("/{x:path}", include_in_schema=False)
async def catchall() -> None:
    raise api.Exception(
        status_code=status.HTTP_404_NOT_FOUND,
        error=api.Error(
            type="catchall", code=InternalErrorCode.INVALID_ROUTE, message="Requested method or path is invalid"
        ),
    )
    
load_langs()

async def main():
    config = Config()
    config.bind = [f"{settings.listening_host}:{settings.listening_port}"]
    config.backlog = 200

    config.logconfig_dict = logging_schema
    config.errorlog = logger
    await serve(app, config)  # type: ignore


if __name__ == "__main__":
    asyncio.run(main())
