import asyncio
from fastapi import APIRouter, Depends, status
from utils.settings import settings
import models.api as api
from datetime import datetime
import subprocess
from os import getpid
import socket
from utils.jwt import JWTBearer


router = APIRouter()

service_start_time : datetime = datetime.now()
branch_cmd = "git rev-parse --abbrev-ref HEAD"
result = subprocess.run(
    [branch_cmd], capture_output=True, text=True, shell=True
)
branch = result.stdout.split("\n")[0]

version_cmd = "git rev-parse --short HEAD"
result = subprocess.run([version_cmd], capture_output=True, text=True, shell=True)
version = result.stdout.split("\n")[0]

tag_cmd = "git name-rev --tags --name-only $(git rev-parse HEAD)"
result = subprocess.run([tag_cmd], capture_output=True, text=True, shell=True)
tag = result.stdout.split("\n")[0]

server = socket.gethostname()

@router.get("/me", include_in_schema=False, response_model=api.Response, response_model_exclude_none=True)
async def get_me(shortname=Depends(JWTBearer())) -> api.Response:
    return api.Response(status=api.Status.success, attributes={"shortname":shortname})

@router.get("/settings", include_in_schema=False, response_model=api.Response, response_model_exclude_none=True)
async def get_settings(shortname=Depends(JWTBearer())) -> api.Response:
    if shortname != 'dmart': 
        raise api.Exception(status_code=status.HTTP_401_UNAUTHORIZED, error=api.Error(type="access", code=401, message="Not allowed"))
    return api.Response(status=api.Status.success, attributes=settings.dict())

@router.get("/manifest", include_in_schema=False, response_model=api.Response, response_model_exclude_none=True)
async def get_manifest(_=Depends(JWTBearer())) -> api.Response:
    now = datetime.now()
    manifest = {
            "name": "DMART",
            "type": "microservice",
            "description": "Structured CMS/IMS",
            "start_time": service_start_time.isoformat(),
            "current_time": now.isoformat(),
            "running_for": str(now - service_start_time),
            "versoin": version,
            "branch": branch,
            "tag": tag,
            "server": server,
            "process": getpid()
            }
    return api.Response(status=api.Status.success,
                        attributes=manifest)


@router.get("/in-loop-tasks", include_in_schema=False)
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
