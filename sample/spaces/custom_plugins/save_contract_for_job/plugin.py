import json
import os
import re
import shutil

import aiofiles
from PIL import Image
from models import core
from models.core import PluginBase, Event, Record
from utils import repository, db
from utils.db import load_resource_payload
from utils.helpers import branch_path
from fastapi.logger import logger
from utils.settings import settings
from dicttoxml import dicttoxml
from pdf2image.pdf2image import convert_from_path
from datetime import datetime
from pathlib import Path
from weasyprint import HTML

class Plugin(PluginBase):
    XML_DATA: dict = {}
    attachments: dict = {}
    folder_dist: Path

    def __init__(self) -> None:
        super().__init__()
        with open(Path(__file__).parent / "config.json") as file:
            config_data = json.load(file)

        self.config_data: dict = config_data

    async def hook(self, data: Event):

        # Type narrowing for PyRight
        if not isinstance(data.shortname, str) or not isinstance(data.attributes, dict):
            logger.error(f"invalid data at save_contract_for_job")
            return

        contract_meta: core.Ticket = await db.load(
            space_name=data.space_name,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=core.Ticket,
            user_shortname=data.user_shortname,
            branch_name=settings.management_space_branch,
        )
        contract_payload = load_resource_payload(
            space_name=data.space_name,
            subpath=data.subpath,
            filename=contract_meta.payload.body,  # type: ignore
            class_type=core.Ticket,
            branch_name=data.branch_name
        )
        ticket_locator: dict = contract_payload.get("ticket_locator", {})
        if not ticket_locator or not ticket_locator.get("subpath") or not ticket_locator.get('shortname'):
            return
        ticket_name = ticket_locator.get('subpath', '/').split('/')[1]

        if contract_meta.state != 'pending' or ticket_name not in self.config_data["available_tickets"]:
            return

        ticket_meta: core.Ticket = await db.load(
            space_name="b2c",
            subpath=ticket_locator.get('subpath', '/'),
            shortname=ticket_locator.get('shortname', ''),
            class_type=core.Ticket,
            user_shortname=data.user_shortname,
            branch_name=settings.management_space_branch,
        )
        ticket_payload = load_resource_payload(
            space_name="b2c",
            subpath=ticket_locator.get('subpath', '/'),
            filename=ticket_meta.payload.body,  # type: ignore
            class_type=core.Ticket,
            branch_name=data.branch_name
        )

        contract_owner: core.User
        contract_owner: core.User = await db.load(
            space_name=settings.management_space,
            subpath="users",
            shortname=contract_meta.owner_shortname,
            class_type=core.User,
            user_shortname=contract_meta.owner_shortname,
            branch_name=settings.management_space_branch,
        )

        contract_meta_path = (
                settings.spaces_folder
                / data.space_name
                / branch_path(settings.default_branch)
                / "tickets"
                / ".dm"
        )

        self.attachments = await repository.get_entry_attachments(
            subpath=f"{data.subpath}/{data.shortname}",
            branch_name=settings.default_branch,
            attachments_path=(contract_meta_path / contract_meta.shortname),
        )

        contract_number = data.shortname.zfill(9)
        date = contract_meta.created_at.strftime("%y%m%d")
        time = contract_meta.created_at.strftime("%H%M%S")
        folder_name = f'{str(contract_owner.uuid)[:8]}{contract_number}{str(date)}_{str(time)}'
        self.folder_dist = (Path(self.config_data["contracts_folder"]) / folder_name)
        if not self.folder_dist.is_dir():
            os.makedirs(self.folder_dist)

        media: Record
        attach_number = 0
        for media in self.attachments.get('media', {}):
            payload = media.attributes.get('payload')
            if not payload or not hasattr(payload, "body"):
                continue
            file_name: str = payload.body
            ext = file_name.split(".")[-1]
            mefs_file_name = self.fix_attachment_name(file_name)
            if mefs_file_name:
                mefs_file_name = f'{mefs_file_name}.{ext}'
            else:
                # TODO: for change ownership two side cuz we will have two counter for sides
                attach_number += 1
                mefs_file_name = f'Attach{str(attach_number).zfill(2)}.{ext}'

            if ext == 'png' or ext == 'jpeg' or ext == 'jpg':
                image = Image.open((contract_meta_path / contract_meta.shortname) / "attachments.media" / file_name)
                mefs_file_name = mefs_file_name.split(".")[0]
                image = self.resize_image(image)
                image.convert('RGB').save(f"{self.folder_dist / mefs_file_name}.jpg")
            else:
                shutil.copy((contract_meta_path / contract_meta.shortname) / "attachments.media" / file_name,
                            self.folder_dist / mefs_file_name)

        self.fill_xml(
            contract_payload=contract_payload,
            contract_meta=contract_meta,
            ticket_payload=ticket_payload,
            ticket_meta=ticket_meta,
            contract_owner=contract_owner,
            attach_number=len(self.attachments.get('media', {}))
        )

        # process information service tickets and sim registration [b2b]
        if 'change_ownership' in ticket_name:
            result_data = self.apply_change_ownership(contract_meta, ticket_payload, contract_payload)
        else:
            result_data = self.apply_other_tickets(contract_meta, ticket_payload, contract_payload)

        # save data.xml file
        if result_data.get('xml_data'):
            xml = dicttoxml(result_data.get('xml_data')).decode()
            xml_file = open((self.folder_dist / "data.xml"), "w")
            xml = xml.replace(' type="str"', '')
            xml_file.write(xml)
            xml_file.close()

        # save pdfs
        for pdf in result_data.get('pdf_templates', {}):
            try:
                await self.generate_pdf_file(
                    template_name=pdf.get('template'),
                    output_path=(self.folder_dist / f"{pdf.get('output_name')}.pdf"),
                    params=pdf.get('params')
                )
            except Exception as e:
                pass
            try:
                # convert pdf to image
                images = convert_from_path(self.folder_dist / f"{pdf.get('output_name')}.pdf")
                if len(images) > 0:
                    attach_number += 1
                    mefs_file_name = f'Attach{str(attach_number).zfill(2)}'
                    image = self.resize_image(images[0])
                    image.save(f"{self.folder_dist / mefs_file_name}.jpg", 'JPEG')
            except Exception as e:
                logger.error(f"Plugin:save_contract_for_job:{str(e)}")

        # generate zip file
        shutil.make_archive((f"{self.config_data['contracts_folder']}/C{folder_name}"), 'zip', self.folder_dist)

    def resize_image(self, image):
        base_width = 700
        if image.width > base_width:
            wpercent = (base_width / float(image.width))
            hsize = int((float(image.height) * float(wpercent)))
            return image.resize((base_width, hsize), Image.Resampling.LANCZOS)
        return image

    def fix_attachment_name(self, file_name):
        if 'second_fingerprint' in file_name:
            return 'SECOND_FINGERPRINT'
        elif 'second_signature' in file_name:
            return 'SECOND_SIGNATURE'
        elif 'second_live_photo' in file_name:
            return 'SECOND_CUST_PHOTO'
        elif 'fingerprint' in file_name:
            return 'FINGERPRINT'
        elif 'signature' in file_name:
            return 'SIGNATURE'
        elif 'live_photo' in file_name:
            return 'CUST_PHOTO'
        else:
            return None

    def select_contract_type(self, schema_shortname: str | None, ticket_body: dict):
        if not schema_shortname:
            return ''
        if 'b2b' in schema_shortname.lower():
            contract_type: str = ticket_body.get('company_data', {}).get('contract_type', "")
            if contract_type.lower() == 'postpaid':
                return 'POST-PAID'
            elif contract_type.lower() == 'prepaid':
                return 'PRE-PAID'
        elif 'dummy' in schema_shortname.lower():
            return 'SERV_DU'
        elif 'correct_info' in schema_shortname.lower():
            return 'SERV_CI'
        elif 'migration' in schema_shortname.lower():
            return 'SERV_MI'
        elif 'change_ownership' in schema_shortname.lower():
            return 'SERV_CO'
        return ''

    def find_attachment_path(self, key):
        for media in self.attachments.get('media', {}):
            file_name = media.attributes.get('payload', {}).body
            mefs_file_name = self.fix_attachment_name(file_name)
            if key.lower() in file_name.lower():
                return str(self.folder_dist.absolute() / f'{mefs_file_name}.jpg')
        return ""

    def fill_xml(
            self,
            contract_payload: dict,
            contract_meta: core.Ticket,
            ticket_payload: dict,
            ticket_meta: core.Ticket,
            contract_owner: core.User,
            attach_number
    ):
        contract_owner_name = ''
        owner_shortname = ''
        pos_phone = ''
        shortname = ''
        cont_date = ''
        ent_start = ''
        birth_date = ''
        username = ''
        contract_type = ''

        if contract_meta:
            shortname = contract_meta.shortname

        if contract_owner and contract_owner.displayname and contract_owner.displayname.en:
            contract_owner_name = contract_owner.displayname.en

        if contract_owner and contract_owner.msisdn:
            pos_phone = contract_owner.msisdn

        if contract_owner and contract_owner.uuid:
            owner_shortname = str(contract_owner.uuid)[:8]

        if contract_meta and contract_meta.collaborators and contract_meta.collaborators.get('locked_by'):
            username = contract_meta.collaborators.get('locked_by')

        if contract_meta and contract_meta.created_at:
            cont_date = contract_meta.created_at.strftime("%d/%m/%Y")
            ent_start = contract_meta.created_at.strftime("%d/%m/%Y %H:%M")

        if contract_payload.get('birth_date'):
            try:
                birth_date = datetime.strptime(contract_payload.get('birth_date', ''), '%Y-%m-%d')
                birth_date = birth_date.strftime("%d/%m/%Y")
            except Exception as e:
                pass

        if ticket_meta.payload:
            contract_type = self.select_contract_type(ticket_meta.payload.schema_shortname, ticket_payload)

        self.XML_DATA = {
            'CONT_TYPE': contract_type,
            'ENT_START': ent_start,
            'CONT_DATE': cont_date,
            'CONT_NUM': owner_shortname + shortname.zfill(9),
            'SUB_TYPE': contract_payload.get('customer_type', ""),
            'SUB_ID': str(ticket_payload.get('irm_info', {}).get('IDNumber', "")),
            'GENDER': contract_payload.get('gender', ""),
            'ICCID': contract_payload.get('iccid', ""),
            'MSISDN': contract_payload.get('msisdn', ""),
            'SUB_NAME': contract_payload.get('customer_name', ""),
            'SUB_EMAIL': '',
            'M_NAME': contract_payload.get('mother_name', ""),
            'BIRTH_DATE': birth_date,
            'BIRTH_PLACE': contract_payload.get('birth_place', ""),
            'NATION': contract_payload.get('nationality', ""),
            'IDPAGENO': contract_payload.get('id_page_no', ""),
            'RECORDNO': contract_payload.get('record_number', ""),
            'HOUSE': contract_payload.get('address', {}).get('building_number', ""),
            'Street_Text': contract_payload.get('address', {}).get('street_name', ""),
            'DISTRICT1': "",
            'DISTRICT2': "",
            'CITY': contract_payload.get('address', {}).get('city', ""),
            'GOVERN': contract_payload.get('address', {}).get('governorate_shortname', ""),
            'PHONENUM': contract_payload.get('msisdn', ""),
            'NEARPOINT': "",
            'RCARD_NUM': str(contract_payload.get('residence_number', "")),
            'POS_ID': owner_shortname,
            'USER_ID': owner_shortname,
            'POS_NAME': contract_owner_name,
            'NO_ATTCH': str(attach_number),
            'USERNAME': username,
            'POS_PHONE': pos_phone,
            'COMPNAME': "",
            'CO_HOUSE': "",
            'CO_STREET': "",
            'CO_DISTRT1': "",
            'CO_DISTRT2': "",
            'CO_CITY': "",
            'CO_GOVERN': "",
            'CO_PHONE': "",
            'CO_LICNO': "",
            'CO_ISSUEDT': "",
            'CO_WEBSITE': "",
            'CO_EMAIL': "",
            'CO_FAX': "",
            'PAYTYPE': "",
            'BANK': "",
            'BBRANCH': "",
            'BADDRESS': "",
            'ACCT_NO': "",
            'COM_REC': "",
            'TAX_CARD': "",
            'OFF_AUTH': "",
            'IDENTITY': "",
            'Dev_ID_Text': "",
            'ACTIVATE': "",
            'PRINTED': "",
            'APP_ID': "",
            'NATION_ID': "",
            'GOVERN_ID': "",
            'CO_GOVERN_ID': "",
            'AndroidDeviceID': "",
            'SIMICCID': "",
            'McrApkVersion': "",
            'PrintedOn': "",
            'fingerPrintData': "",
        }

    def apply_other_tickets(
            self,
            meta: core.Ticket,
            ticket_payload: dict,
            contract_payload: dict
    ):
        pdf_templates = []
        xml_data = self.XML_DATA.copy()

        params = {
            'customer_name': contract_payload.get('customer_name', ticket_payload.get('customer_name', "")),
            'fingerprint': self.find_attachment_path('fingerprint'),
            'signature': self.find_attachment_path('signature'),
            'iccid': contract_payload.get('iccid', ticket_payload.get('iccid', "")),
            'msisdn': contract_payload.get('msisdn', ticket_payload.get('msisdn', "")),
            'created_at': str(meta.created_at.strftime("%d/%m/%Y")),
            'id_creation_date': contract_payload.get('id_creation_date', ""),
        }

        pdf_templates.append(
            {'template': 'commitment_letter', 'output_name': 'Commitment_Letter', 'params': params}
        )
        return {'pdf_templates': pdf_templates, 'xml_data': xml_data}

    def apply_change_ownership(
            self,
            meta: core.Ticket,
            ticket_payload: dict,
            contract_payload: dict
    ):
        pdf_templates = []
        xml_data = self.XML_DATA.copy()

        if ticket_payload.get('service_type') == 'two_side':
            params = {
                'signature': self.find_attachment_path('signature'),
                'second_signature': self.find_attachment_path('second_signature'),
                'fingerprint': self.find_attachment_path('fingerprint'),
                'second_fingerprint': self.find_attachment_path('second_fingerprint'),
                'user_shortname': meta.owner_shortname,
                'customer_name': ticket_payload.get('customer_name'),
                'customer_name_second_party': ticket_payload.get('customer_name_second_party'),
                'iccid': ticket_payload.get('iccid'),
                'iccid_second_party': ticket_payload.get('iccid_second_party'),
                'msisdn': ticket_payload.get('msisdn'),
                'msisdn_second_party': ticket_payload.get('msisdn_second_party'),
                'address': ticket_payload.get('address'),
                'address_second_party': ticket_payload.get('address_second_party')
            }
            pdf_templates.append(
                {'template': 'assignment_letter', 'output_name': 'Assignment_Letter', 'params': params}
            )
            params = {
                'customer_name': ticket_payload.get('customer_name_second_party', ""),
                'fingerprint': self.find_attachment_path('second_fingerprint'),
                'signature': self.find_attachment_path('second_signature'),
                'iccid': ticket_payload.get('iccid_second_party', ""),
                'msisdn': ticket_payload.get('msisdn_second_party', ""),
                'created_at': str(meta.created_at.strftime("%d/%m/%Y")),
                'id_creation_date': contract_payload.get('id_creation_date'),
            }

            pdf_templates.append(
                {'template': 'commitment_letter', 'output_name': 'Commitment_Letter', 'params': params}
            )
        elif ticket_payload.get('service_type') == 'one_side':

            params = {
                'customer_name': contract_payload.get('customer_name', ticket_payload.get('customer_name', "")),
                'fingerprint': self.find_attachment_path('fingerprint'),
                'signature': self.find_attachment_path('signature'),
                'iccid': contract_payload.get('iccid', ticket_payload.get('iccid', "")),
                'msisdn': contract_payload.get('msisdn', ticket_payload.get('msisdn', "")),
                'created_at': str(meta.created_at.strftime("%d/%m/%Y")),
                'id_creation_date': contract_payload.get('id_creation_date', ""),
            }

            pdf_templates.append(
                {'template': 'commitment_letter', 'output_name': 'Commitment_Letter', 'params': params}
            )
        return {'pdf_templates': pdf_templates, 'xml_data': xml_data}

    async def generate_pdf_file(self,
            params: dict[str, str],
            template_name: str,
            output_path: Path | None = None
    ):
        if not output_path:
            raise Exception('output_path is not provided')

        html_path = Path(f'{settings.spaces_folder}/{settings.management_space}/templates/pdf/{template_name}.html')
        async with aiofiles.open(html_path, "r") as file:
            template_content = await file.read()

        for key in params:
            template_content = template_content.replace('{' + key + '}', params[key])

        template_content = re.sub(r"\{.*\}", '', template_content)

        html = HTML(string=template_content, base_url=str(Path(f'pdf_templates').absolute()))
        await html.write_pdf(target=output_path)

