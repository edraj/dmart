from time import time
from fastapi import APIRouter, Depends, Path, Body, status
from fastapi.responses import StreamingResponse
from api.managed.router import retrieve_entry_meta
from utils.internal_error_code import InternalErrorCode
from utils.jwt import JWTBearer
from io import BytesIO
import models.api as api
import utils.regex as regex
import hmac
import hashlib
from utils.settings import settings
from models.enums import ResourceType
from fastapi.responses import ORJSONResponse

router = APIRouter(default_response_class=ORJSONResponse)


@router.get("/generate/{resource_type}/{space_name}/{subpath:path}/{shortname}")
async def generate_qr_user_profile(
    resource_type: ResourceType = Path(...),
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
    shortname: str = Path(..., pattern=regex.SHORTNAME,
                          examples=["unique_shortname"]),
    logged_in_user=Depends(JWTBearer()),
) -> StreamingResponse:
    data: str | dict = await retrieve_entry_meta(
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
            api.Error(type="qr", code=InternalErrorCode.QR_ERROR,
                      message="QR cannot be generated"),
        )
    m = hmac.new(settings.jwt_secret.encode(), digestmod=hashlib.sha256)
    data = f"{resource_type}/{space_name}/{subpath}/{shortname}"
    date = int(time())
    m.update(f"{date}.{data}".encode())
    hexed_data = m.hexdigest()

    try:
        segno = __import__("segno")
        qrcode = segno.make(f"{date}.{hexed_data}")
        v_path = BytesIO()
        qrcode.save(v_path, kind="png", dpi=600, scale=10)

        return StreamingResponse(iter([v_path.getvalue()]), media_type="image/png")
    except ModuleNotFoundError:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="segno is not installed!",
            ),
        )


@router.post("/validate")
async def validate_qr_user_profile(
    resource_type: ResourceType = Body(...),
    space_name: str = Body(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Body(..., pattern=regex.SUBPATH, examples=["/content"]),
    shortname: str = Body(..., pattern=regex.SHORTNAME,
                          examples=["unique_shortname"]),
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
            api.Error(type="qr", code=InternalErrorCode.QR_EXPIRED,
                      message="QR did expire"),
        )
    data = f"{resource_type}/{space_name}/{subpath}/{shortname}"
    m = hmac.new(settings.jwt_secret.encode(), digestmod=hashlib.sha256)
    m.update(f"{req_date}.{data}".encode())
    hexed_data = m.hexdigest()

    if hexed_data == req_data:
        return api.Response(status=api.Status.success)
    else:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(type="qr", code=InternalErrorCode.QR_INVALID,
                      message="Invalid data passed"),
        )
