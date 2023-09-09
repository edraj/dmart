from time import time
from fastapi import APIRouter, Depends, Path, Body, status
from fastapi.responses import StreamingResponse
from api.managed.router import retrieve_entry_meta
from utils.jwt import JWTBearer
from io import BytesIO
import segno
import models.api as api
import utils.regex as regex
import hmac
import hashlib
from utils.settings import settings
from models.enums import ResourceType

router = APIRouter()


@router.get("/generate/{resource_type}/{space_name}/{subpath:path}/{shortname}")
async def generate_qr_user_profile(
    resource_type: ResourceType = Path(...),
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    logged_in_user=Depends(JWTBearer()),
) -> StreamingResponse:
    data : str | dict = await retrieve_entry_meta(
        resource_type,
        space_name,
        subpath,
        shortname,
        logged_in_user=logged_in_user,
    )

    if (
        isinstance(data, dict)
        and data.get("owner_shortname") != logged_in_user
        and f"management/{subpath}/{data['shortname']}"
        != f"{space_name}/users/{logged_in_user}"
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(type="qr", code=14, message="QR cannot be generated"),
        )
    m = hmac.new(settings.jwt_secret.encode(), digestmod=hashlib.blake2s)
    data = f"{resource_type}/{space_name}/{subpath}/{shortname}"
    date = int(time())
    m.update(f"{date}.{data}".encode())
    hexed_data = m.hexdigest()
    qrcode = segno.make(f"{date}.{hexed_data}")
    v_path = BytesIO()
    qrcode.save(v_path, kind="png", dpi=600, scale=10)

    return StreamingResponse(iter([v_path.getvalue()]), media_type="image/png")


@router.post("/validate")
async def validate_qr_user_profile(
    resource_type: ResourceType = Body(...),
    space_name: str = Body(..., pattern=regex.SPACENAME),
    subpath: str = Body(..., pattern=regex.SUBPATH),
    shortname: str = Body(..., pattern=regex.SHORTNAME),
    logged_in_user=Depends(JWTBearer()),
    qr_data: str = Body(..., embed=True),
):
    await retrieve_entry_meta(
        resource_type,
        space_name,
        subpath,
        shortname,
        logged_in_user=logged_in_user,
    )
    arr_data = qr_data.split(".")
    req_date, req_data = arr_data[0], arr_data[1]
    if int(req_date) + 60 < int(time()):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(type="qr", code=15, message="QR did expire"),
        )
    data = f"{resource_type}/{space_name}/{subpath}/{shortname}"
    m = hmac.new(settings.jwt_secret.encode(), digestmod=hashlib.blake2s)
    m.update(f"{req_date}.{data}".encode())
    hexed_data = m.hexdigest()

    if hexed_data == req_data:
        return api.Response(status=api.Status.success)
    else:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(type="qr", code=16, message="Invalid data passed"),
        )
