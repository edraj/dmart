import re
import aiofiles
import models.api as api
import models.core as core
import utils.db as db
import utils.regex as regex
import utils.repository as repository
from pathlib import Path as PathLib
from fastapi import APIRouter, Path, Depends, status
from starlette.responses import StreamingResponse
from weasyprint import HTML
from io import BytesIO
from pypdf import PdfWriter, PdfReader
from weasyprint.text.fonts import FontConfiguration
from utils.jwt import JWTBearer
from utils.helpers import (
    branch_path,
)
from utils.settings import settings

router = APIRouter()


async def generate_pdf_byte(params: dict[str, str], template_name: str, appended_pdf: list[str]):
    html_path = PathLib(f'{settings.spaces_folder}/{settings.management_space}/templates/pdf/{template_name}.html')
    async with aiofiles.open(html_path, "r") as file:
        template_content = await file.read()

    for key in params:
        if params[key] is None:
            params[key] = ''
        template_content = template_content.replace('{' + key + '}', params[key])

    template_content = re.sub(r"\{.*\}", "", template_content)

    font_config = FontConfiguration()
    html = HTML(string=template_content, base_url=str(PathLib(f'pdf_templates').absolute()))
    generated_pdf: bytes = html.write_pdf(font_config=font_config)
    # merge the pdfs
    try:
        reader = PdfReader(BytesIO(generated_pdf))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for pdf in appended_pdf:
            writer.append(open(pdf, "rb"))
        bytes_stream = BytesIO()
        writer.write(bytes_stream)
        yield bytes_stream.getbuffer().tobytes()
    except Exception as e:
        yield generated_pdf


@router.get(
    "/generate-pdf-ticket/{subpath:path}/{shortname}",
    response_model_exclude_none=True,
)
async def get_pdf_api(
        subpath: str = Path(..., regex=regex.SUBPATH),
        shortname: str = Path(..., regex=regex.SHORTNAME),
        logged_in_user=Depends(JWTBearer()),
) -> StreamingResponse:
    space_name = "b2c"
    tickets = {
        "sim_swap": "Sim Swap",
        "change_ownership": "Change Ownership",
        "check_info": "Check info",
        "connect_disconnect": "Connect/Disconnect",
        "migration": "Migration",
        "postpaid_prime": "Postpaid prime",
        "correct_info": "Correct info",
        "rc_compensation": "RC Compensation",
        "dummy": "Dummy",
        "add_remove_vas": "Add/Remove VAS"
    }

    meta: core.Ticket = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=core.Ticket,
        user_shortname=logged_in_user,
        branch_name=settings.default_branch,
    )
    # Type narrowing for PyRight
    if (
            not isinstance(meta.payload, core.Payload)
            or not isinstance(meta.payload.body, str)
            or not isinstance(meta.payload.schema_shortname, str)
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=203,
                message="Invalid entry",
            ),
        )

    payload = db.load_resource_payload(
        space_name=space_name,
        subpath=subpath,
        filename=meta.payload.body,
        class_type=core.Ticket,
        branch_name=settings.default_branch,
    )
    meta_path = (
            settings.spaces_folder
            / space_name
            / branch_path(settings.default_branch)
            / subpath
            / ".dm"
    )
    attachments = await repository.get_entry_attachments(
        subpath=f"{subpath}/{shortname}",
        branch_name=settings.default_branch,
        attachments_path=(meta_path / shortname),
    )
    params: dict[str, str] = {}
    pdfs: list[str] = []

    # append from meta
    if meta.reporter:
        params["pos_name"] = meta.reporter.name or ''
        params["pos_type"] = meta.reporter.type or ''
        params["distributors"] = meta.reporter.distributor or ''

    if not params.get("pos_name"):
        params["pos_name"] = meta.owner_shortname

    params["admin_user"] = ""
    if meta.collaborators and meta.collaborators.get("locked_by"):
        params["admin_user"] = meta.collaborators.get("locked_by", "")

    params["status"] = meta.state
    params["date"] = str(meta.created_at.replace(microsecond=0))

    # append from payload
    params["iccid"] = payload.get("iccid", "")
    params["msisdn"] = payload.get("msisdn", "")
    params["name"] = payload.get("customer_name", "")
    # append attachments
    i = 1
    attachment: core.Record
    for attachment in attachments.get("media", {}):
        body = attachment.attributes.get("payload", {}).body  # type: ignore
        if body:
            path = str((meta_path / shortname / "attachments.media" / body).absolute())
            if body[-4:] == ".pdf":
                pdfs.append(path)
                continue
            if "live_photo" in body:
                params["live_photo"] = path
            elif "signature" in body:
                params["signature"] = path
            elif "fingerprint" in body:
                params["fingerprint"] = path
            else:
                params["attachment_" + str(i)] = path
                params["attachment_name_" + str(i)] = body
                i += 1

    params["ticket_type"] = tickets[meta.payload.schema_shortname]
    byte = generate_pdf_byte(
        params=params, template_name="aftersales", appended_pdf=pdfs
    )
    response = StreamingResponse(byte, media_type="application/pdf")
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={meta.payload.schema_shortname}_{meta.shortname}.pdf"

    return response
