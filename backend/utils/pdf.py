import re
import aiofiles

from pathlib import Path
from io import BytesIO
from pypdf import PdfWriter, PdfReader
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from utils.settings import settings


async def generate_pdf_byte(params: dict[str, str], template_name: str, appended_pdf: list[str]):
    html_path = Path(f'{settings.spaces_folder}/{settings.management_space}/templates/pdf/{template_name}.html')

    async with aiofiles.open(html_path, "r") as file:
        template_content = await file.read()

    for key in params:
        if params[key] is None:
            params[key] = ''
        template_content = template_content.replace('{' + key + '}', params[key])

    template_content = re.sub(r"\{.*\}", "", template_content)

    font_config = FontConfiguration()
    html = HTML(string=template_content, base_url=str(Path(f'pdf_templates').absolute()))
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


async def generate_pdf_file(
        params: dict[str, str],
        template_name: str,
        output_path: Path | None = None
):
    if not output_path:
        raise Exception('output_path is not provided')

    html_path = Path(f'pdf_templates/{template_name}.html')
    async with aiofiles.open(html_path, "r") as file:
        template_content = await file.read()

    for key in params:
        template_content = template_content.replace('{' + key + '}', params[key])

    template_content = re.sub(r"\{.*\}", '', template_content)

    html = HTML(string=template_content, base_url=str(Path(f'pdf_templates').absolute()))
    await html.write_pdf(target=output_path)
