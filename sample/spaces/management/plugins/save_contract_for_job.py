import os
import shutil
from pathlib import Path

from PIL import Image

from models import core
from models.core import PluginBase, Event, Record
from utils import repository, db
from utils.db import load_resource_payload
from utils.helpers import branch_path
from utils.logger import logger
from utils.pdf import generate_pdf_file
from utils.settings import settings
from dicttoxml import dicttoxml
from pdf2image import convert_from_path


class Plugin(PluginBase):
    available_tickets = ["change_ownership", "dummy", "migration", "correct_info", "b2b"]
    XML_DATA: dict = {}
    attachments: dict = {}
    folder_dist: Path

    async def hook(self, data: Event):

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
        ticket_locator: dict = contract_payload.get("ticket_locator")
        if not ticket_locator or not ticket_locator.get("subpath") or not ticket_locator.get('shortname'):
            return
        ticket_name = ticket_locator.get('subpath').split('/')[1]
        if contract_meta.state != 'approved' or ticket_name not in self.available_tickets:
            return

        ticket_meta: core.Ticket = await db.load(
            space_name=data.space_name,
            subpath=ticket_locator.get('subpath'),
            shortname=ticket_locator.get('shortname'),
            class_type=core.Ticket,
            user_shortname=data.user_shortname,
            branch_name=settings.management_space_branch,
        )
        ticket_payload = load_resource_payload(
            space_name=data.space_name,
            subpath=ticket_locator.get('subpath'),
            filename=ticket_meta.payload.body,  # type: ignore
            class_type=core.Ticket,
            branch_name=data.branch_name
        )

        contract_owner: core.User = None
        try:
            contract_owner: core.User = await db.load(
                space_name=settings.management_space,
                subpath="users",
                shortname=contract_meta.owner_shortname,
                class_type=core.User,
                user_shortname=contract_meta.owner_shortname,
                branch_name=settings.management_space_branch,
            )
        except Exception as e:
            logger.error(f"Plugin:save_contract_for_job:{str(e)}")

        contract_meta_path = (
                settings.spaces_folder
                / data.space_name
                / branch_path(settings.default_branch)
                / "contracts"
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
        folder_name = f'{data.user_shortname}{contract_number}{str(date)}_{str(time)}'
        self.folder_dist = (settings.contracts_folder / folder_name)
        if not self.folder_dist.is_dir():
            os.makedirs(self.folder_dist)

        media: Record
        attach_number = 0
        for media in self.attachments.get('media', {}):
            file_name: str = media.attributes.get('payload', {}).body
            if not file_name:
                continue
            ext = file_name.split(".")[-1]
            mefs_file_name = self.fix_attachment_name(file_name)
            if mefs_file_name:
                mefs_file_name = f'{mefs_file_name}.{ext}'
            else:
                # TODO: for change ownership two side cuz we will have two counter for sides
                attach_number += 1
                mefs_file_name = f'Attach{str(attach_number).zfill(2)}.{ext}'

            if ext == 'png' or ext == 'jpeg':
                image = Image.open((contract_meta_path / contract_meta.shortname) / "attachments.media" / file_name)
                mefs_file_name = mefs_file_name.split(".")[0]
                image.convert('RGB').save(f"{self.folder_dist / mefs_file_name}.jpg")
            else:
                shutil.copy((contract_meta_path / contract_meta.shortname) / "attachments.media" / file_name,
                            self.folder_dist / mefs_file_name)

        self.fill_xml(contract_payload, contract_meta, ticket_payload, contract_owner, len(self.attachments.get('media', {})))

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
                await generate_pdf_file(
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
                    images[0].save(f"{self.folder_dist / mefs_file_name}.jpg", 'JPEG')
            except Exception as e:
                logger.error(f"Plugin:save_contract_for_job:{str(e)}")

        # generate zip file
        shutil.make_archive(str(self.folder_dist), 'zip', self.folder_dist)

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
            contract_meta: core.Meta,
            ticket_payload: dict,
            contract_owner: core.User,
            attach_number
    ):
        contract_owner_name = ''
        owner_shortname = ''
        shortname = ''
        if contract_meta:
            shortname = contract_meta.shortname

        if contract_owner and contract_owner.displayname and contract_owner.displayname.en:
            contract_owner_name = contract_owner.displayname.en

        if contract_meta and contract_meta.owner_shortname:
            owner_shortname = contract_meta.owner_shortname

        self.XML_DATA = {
            'CONT_TYPE': contract_payload.get('customer_id_type', ""),
            'CONT_NUM': owner_shortname + shortname,
            'SUB_TYPE': contract_payload.get('customer_type', ""),
            'SUB_ID': str(ticket_payload.get('irm_info', {}).get('IDNumber', "")),
            'GENDER': contract_payload.get('gender', ""),
            'ICCID': contract_payload.get('iccid', ""),
            'MSISDN': contract_payload.get('msisdn', ""),
            'M_NAME': contract_payload.get('mother_name', ""),
            'BIRTH_DATE': contract_payload.get('birth_date', ""),
            'BIRTH_PLACE': contract_payload.get('birth_place', ""),
            'IDPAGENO': contract_payload.get('id_page_no', ""),
            'RECORDNO': contract_payload.get('record_number', ""),
            'HOUSE': contract_payload.get('address', {}).get('building_number', ""),
            'Street_Text': contract_payload.get('address', {}).get('street_name', ""),
            'CITY': contract_payload.get('address', {}).get('city', ""),
            'GOVERN': contract_payload.get('address', {}).get('governorate_shortname', ""),
            'PHONENUM': contract_payload.get('msisdn', ""),
            'RCARD_NUM': str(contract_payload.get('residence_number', "")),
            'POS_ID': owner_shortname,
            'POS_NAME': contract_owner_name,
            'NO_ATTCH': str(attach_number)
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
