# import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, Depends, status
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
import models.api as api
from datetime import datetime
import subprocess
from os import getpid
import socket
from utils.jwt import JWTBearer
from fastapi.responses import ORJSONResponse

router = APIRouter(default_response_class=ORJSONResponse)

git_info: dict[str,str|None] = {}
service_start_time: datetime = datetime.now()

info_json_path = Path(__file__).resolve().parent.parent.parent / "info.json"
if info_json_path.exists():
    with open(info_json_path) as info:
        git_info = json.load(info)
else:
    branch_cmd = "git rev-parse --abbrev-ref HEAD"
    result, _ = subprocess.Popen(branch_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    branch = None if result is None or len(result) == 0 else result.decode().strip()

    version_cmd = "git rev-parse --short HEAD"
    result, _ = subprocess.Popen(version_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    version = None if result is None or len(result) == 0 else result.decode().strip()

    tag_cmd = "git describe --tags"
    result, _ = subprocess.Popen(tag_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    tag = None if result is None or len(result) == 0 else result.decode().strip()

    version_date_cmd = "git show --pretty=format:'%ad'"
    result, _ = subprocess.Popen(version_date_cmd.split(" "), stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE).communicate()
    version_date = None if result is None or len(result) == 0 else result.decode().split("\n")[0]

    git_info = {
        "commit_hash": version,
        "date": version_date,
        "branch": branch,
        "tag": tag
    }

server = socket.gethostname()


@router.get("/me", response_model=api.Response, response_model_exclude_none=True)
async def get_me(shortname=Depends(JWTBearer())) -> api.Response:
    return api.Response(status=api.Status.success, attributes={"shortname": shortname})


@router.get("/settings", response_model=api.Response, response_model_exclude_none=True)
async def get_settings(shortname=Depends(JWTBearer())) -> api.Response:
    if shortname != 'dmart':
        raise api.Exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error=api.Error(
                type="access",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [21]"
            )
        )
    return api.Response(status=api.Status.success, attributes=settings.model_dump())


@router.get("/manifest", response_model=api.Response, response_model_exclude_none=True)
async def get_manifest(_=Depends(JWTBearer())) -> api.Response:
    now = datetime.now()
    manifest = {
        "name": "DMART",
        "type": "microservice",
        "description": "Structured CMS/IMS",
        "service_details": {
            "server": server,
            "process_id": getpid(),
            "start_time": service_start_time.isoformat(),
            "current_time": now.isoformat(),
            "running_for": str(now - service_start_time)
        },
        "git": git_info,
    }
    return api.Response(status=api.Status.success, attributes=manifest)

"""
@router.get("/in-loop-tasks")
async def get_in_loop_tasks(_=Depends(JWTBearer())) -> api.Response:
    tasks = asyncio.all_tasks()

    tasks_data: list[dict[str, str]] = []
    for task in tasks:
        tasks_data.append({
            "name": task.get_name(),
            "coroutine": str(task.get_coro()),
            "stack": str(task.get_stack())
        })

    return api.Response(
        status=api.Status.success,
        attributes={
            "tasks_count": len(tasks_data),
            "tasks": tasks_data
        },
    )
"""