import sys
from uuid import uuid4

import aiofiles
import sqlalchemy
from sqlalchemy import text, delete
from database.create_tables import Entries, Histories, Permissions, Roles, Users, Spaces, Attachments
from copy import copy, deepcopy
from object_adapters.base import BaseObjectAdapter
from utils.helpers import (
    arr_remove_common,
    branch_path,
    camel_case,
    flatten_all,
)
from datetime import datetime
from models.enums import ContentType, ResourceType, QueryType
from utils.internal_error_code import InternalErrorCode
from utils.middleware import get_request_data
from utils.settings import settings
import models.core as core
from typing import Any, Type
import models.api as api
import os
import json
from pathlib import Path
from fastapi import status
from utils.regex import ATTACHMENT_PATTERN
from fastapi.logger import logger
from sqlmodel import create_engine, Session, select, SQLModel


class SQLAdapter(BaseObjectAdapter):
    session: Session = None

    def metapath(self, dto: core.EntityDTO) -> tuple[Path, str]:
        pass

    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"

    def get_session(self):
        if self.session is None:
            connection_string = f"{self.postgresql_url}/{settings.database_name}"
            engine = create_engine(connection_string, echo=True)
            self.session = Session(engine)
        return self.session

    def get_table(self, dto) -> Type[Roles | Permissions | Users | Spaces | Entries | Attachments]:
        match dto.class_type:
            case core.Role:
                return Roles
            case core.Permission:
                return Permissions
            case core.User:
                return Users
            case core.Space:
                return Spaces
            case core.Alteration | core.Media | core.Lock | core.Comment | core.Reply | core.Reaction | core.Json | core.DataAsset:
                return Attachments
            case _:
                return Entries

    def get_base_model(self, dto, data, update=None):
        match dto.class_type:
            case core.User:
                return Users.model_validate(data, update=update)
            case core.Role:
                return Roles.model_validate(data, update=update)
            case core.Permission:
                return Permissions.model_validate(data, update=update)
            case core.Space:
                return Spaces.model_validate(data, update=update)
            case core.Alteration | core.Media | core.Lock | core.Comment | core.Reply | core.Reaction | core.Json | core.DataAsset:
                return Attachments.model_validate(data, update=update)
            case _:
                return Entries.model_validate(data, update=update)

    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        """Given a query return the total and the locators
        Parameters
        ----------
        query: api.Query
            Query of type subpath

        Returns
        -------
        Total, Locators

        """
        locators: list[core.Locator] = []
        total: int = 0
        match query.type:
            case api.QueryType.subpath:
                connection_string = f"{self.postgresql_url}/{query.space_name}"
                engine = create_engine(connection_string, echo=True)
                session = Session(engine)

                #!TODO finsih...

        return total, locators

    def folder_path(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            branch_name: str | None = settings.default_branch,
    ):
        pass

    async def get_entry_attachments(
            self,
            subpath: str,
            attachments_path: Path,
            branch_name: str | None = None,
            filter_types: list | None = None,
            include_fields: list | None = None,
            filter_shortnames: list | None = None,
            retrieve_json_payload: bool = False,
    ) -> dict:
        attachments_dict: dict[str, list] = {}
        with self.get_session() as session:
            statement = select(Attachments).where(Attachments.subpath.startswith(subpath))
            results = list(session.exec(statement).all())
            if len(results) == 0:
                return attachments_dict

            for idx, item in enumerate(results):
                attachment_record = Attachments.model_validate(item)
                attachment_json = attachment_record.model_dump()
                attachment = {
                    "resource_type": attachment_json["resource_type"],
                    "uuid": attachment_json["uuid"],
                    "shortname": attachment_json["shortname"],
                    "branch_name": 'master',
                    "subpath": '/'.join(subpath.split('/')[:-1]),
                }
                del attachment_json["resource_type"]
                del attachment_json["uuid"]
                del attachment_json["shortname"]
                del attachment_json["subpath"]
                del attachment_json["relationships"]
                del attachment_json["acl"]
                del attachment_json["space_name"]
                attachment["attributes"] = {**attachment_json}
                if attachment_record.resource_type in attachments_dict:
                    attachments_dict[attachment_record.resource_type].append(attachment)
                else:
                    attachments_dict[attachment_record.resource_type] = [attachment]

        return attachments_dict

    def payload_path(self, dto: core.EntityDTO) -> Path:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / dto.space_name / branch_path(dto.branch_name)

        subpath = copy(dto.subpath)
        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(dto.class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = (
            #     "." + dto.schema_shortname if dto.schema_shortname != "meta" else ""
            # )
            schema_shortname = ""
            attachment_folder = f"{parent_name}/attachments{schema_shortname}.{dto.class_type.__name__.lower()}"
            path = path / parent_subpath / ".dm" / attachment_folder
        else:
            path = path / subpath
        return path

    async def load_or_none(self, dto: core.EntityDTO) -> core.Meta | None:  # type: ignore
        """Load a Meta Json according to the reuqested Class type"""
        print(dto, dto.class_type)
        with self.get_session() as session:
            table = self.get_table(dto)
            statement = select(table).where(table.space_name == dto.space_name)

            if table in [Roles, Permissions, Users, Spaces]:
                statement = statement.where(table.shortname == dto.shortname)
            else:
                if dto.class_type == core.Folder:
                    statement = statement.where(table.shortname == dto.shortname)
                else:
                    if table is Attachments:
                        statement = statement.where(table.shortname == dto.shortname).where(table.subpath == f"{dto.subpath}/attachments.{dto.resource_type}")
                    else:
                        statement = statement.where(table.subpath == dto.subpath).where(table.shortname == dto.shortname)

            result = session.exec(statement).one_or_none()
            if result is None:
                return None

            try:
                try:
                    if result.payload:
                        result.payload = core.Payload.model_validate(result.payload)
                except Exception as e:
                    print("[!load]", e)
                    logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                return result
            except Exception as e:
                print("[!load_or_none]", e)
                logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                return None

    async def query(self, query: api.Query | None = None) -> list[core.MetaChild]:
        with self.get_session() as session:
            table = None
            if query.type == QueryType.spaces:
                table = Spaces
            elif query.space_name == 'management':
                match query.subpath:
                    case "users":
                        table = Users
                    case "roles":
                        table = Roles
                    case "permissions":
                        table = Permissions
                    case _:
                        table = Entries
            else:
                table = Entries
            statement = select(table)

            if query:
                if query.space_name:
                    if query.type != QueryType.spaces or query.space_name != 'management' or query.subpath != "/":
                        statement = statement.where(table.space_name == query.space_name)
                if query.subpath and table is Entries:
                    print(f"{query.subpath=}")
                    statement = statement.where(table.subpath == query.subpath)
                if query.search and query.subpath != "/":
                    statement = statement.where(table.shortname == query.search)
                # if query.filter_schema_names:
                #     statement = statement.where(table.schema_shortname.in_(query.filter_schema_names))
                # if query.filter_shortnames:
                #     statement = statement.where(table.shortname.in_(query.filter_shortnames))
                # if query.filter_tags:
                #     statement = statement.where(table.tags.contains(query.filter_tags))
                # if query.search:
                #     statement = statement.where(table.shortname.ilike(f"%{query.search}%"))
                if query.from_date:
                    statement = statement.where(table.created_at >= query.from_date)
                if query.to_date:
                    statement = statement.where(table.created_at <= query.to_date)
                if query.sort_by:
                    statement = statement.order_by(table.__dict__[query.sort_by])
                if query.sort_type == "descending":
                    statement = statement.order_by(table.__dict__[query.sort_by].desc())
                if query.limit:
                    statement = statement.limit(query.limit)
                if query.offset:
                    statement = statement.offset(query.offset)
            print(f"{statement=}")
            results = list(session.exec(statement).all())
            if len(results) == 0:
                return []

            for idx, item in enumerate(results):
                results[idx] = table.model_validate(item)

        return results

    async def load(self, dto: core.EntityDTO) -> core.MetaChild:
        meta: core.Meta | None = await self.load_or_none(dto)  # type: ignore
        if meta is None:
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available @{dto.space_name}/{dto.subpath}/{dto.shortname} {dto.resource_type=} {dto.schema_shortname=}",
                ),
            )

        return meta
        # type: ignore

    async def load_resource_payload(self, dto: core.EntityDTO) -> dict[str, Any] | None:
        """Load a Meta class payload file"""
        with self.get_session() as session:
            table = self.get_table(dto)
            statement = select(table).where(table.space_name == dto.space_name)

            if table in [Roles, Permissions, Users]:
                statement = statement.where(table.shortname == dto.shortname)
            else:
                statement = statement.where(table.subpath == dto.subpath).where(table.shortname == dto.shortname)

            result = session.exec(statement).one_or_none()
            if result is None:
                return None

            return result[0].model_dump().get('payload', {}).get('body', {})

    async def save(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ):
        """Save Meta Json to respectiv file"""
        try:
            with self.get_session() as session:
                print(f"{dto=}")
                entity = {
                    **meta.model_dump(),
                    'space_name': dto.space_name,
                    "subpath": dto.subpath,
                    "resource_type": dto.resource_type
                }
                if entity['payload']:
                    entity['payload']['body'] = payload_data

                if dto.class_type is core.Folder:
                    if entity['subpath'].startswith('/'):
                        entity['subpath'] = entity['subpath'][1:]
                    entity['subpath'] += dto.shortname

                if dto.class_type in [core.Alteration, core.Media, core.Lock, core.Comment, core.Reply, core.Reaction, core.Json, core.DataAsset]:
                    entity['subpath'] = f"{dto.subpath}/attachments.{dto.resource_type}"

                if entity['subpath'].endswith('/'):
                    entity['subpath'] = entity['subpath'][:-1]

                try:
                    data = self.get_base_model(dto, entity)
                    session.add(data)
                    session.commit()
                except Exception as e:

                    logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                    return None

        except Exception as e:
            print("[!save]", e)
            logger.error(f"Failed saving an entry. {dto=}. Error: {e.args}")
            raise api.Exception(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.SOMETHING_WRONG,
                    message=f"Failed saving an entry. {dto=}. Error: {e.args}",
                ),
            )

    async def create(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ):
        result = await self.load_or_none(dto)

        if result is not None:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                    message="already exists",
                ),
            )

        await self.save(dto, meta, payload_data)

    async def save_payload(self, dto: core.EntityDTO, meta: core.Meta, attachment):
        with self.get_session() as session:
            payload_file_path = self.payload_path(dto)
            payload_filename = meta.shortname + Path(attachment.filename).suffix

            os.makedirs(payload_file_path, exist_ok=True)
            async with aiofiles.open(payload_file_path / payload_filename, "wb") as file:
                content = await attachment.read()
                await file.write(content)

                await self.save(dto, meta)

    async def save_payload_from_json(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any]
    ):
        pass

    async def update(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ) -> dict:
        """Update the entry, store the difference and return it"""
        with self.get_session() as session:
            result = await self.load(dto)

            if result is None:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="create",
                        code=InternalErrorCode.MISSING_METADATA,
                        message="metadata is missing",
                    ),
                )
            old = deepcopy(result)
            try:
                meta.space_name = dto.space_name
                meta.updated_at = datetime.now()
                if meta.payload:
                    meta.payload.body = payload_data
                    meta.payload = meta.payload.model_dump()

                result.sqlmodel_update(meta)
                session.add(result)
                session.commit()
            except Exception as e:
                print("[!]", e)
                logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="update",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to update entry",
                    ),
                )

        history_diff = await self.store_entry_diff(
            dto=dto,
            old_meta=old,
            new_meta=meta,
            old_payload={},
            new_payload={},
        )
        return history_diff

    async def store_entry_diff(
            self,
            dto: core.EntityDTO,
            old_meta: core.Meta,
            new_meta: core.Meta,
            old_payload: dict[str, Any] | None = None,
            new_payload: dict[str, Any] | None = None,
    ) -> dict:
        with self.get_session() as session:
            try:
                old_flattened = flatten_all(old_meta.model_dump())
                new_flattened = flatten_all(new_meta.model_dump())

                diff_keys = list(old_flattened.keys())
                diff_keys.extend(list(new_flattened.keys()))
                history_diff = {}
                for key in set(diff_keys):
                    if key in ["updated_at"]:
                        continue
                    # if key in updated_attributes_flattend:
                    old = copy(old_flattened.get(key, "null"))
                    new = copy(new_flattened.get(key, "null"))

                    if old != new:
                        if isinstance(old, list) and isinstance(new, list):
                            old, new = arr_remove_common(old, new)
                        history_diff[key] = {
                            "old": old,
                            "new": new,
                        }
                if not history_diff:
                    return {}

                history_obj = Histories(
                    space_name=dto.space_name,
                    uuid=uuid4(),
                    shortname="history",
                    owner_shortname=dto.user_shortname or "__system__",
                    timestamp=datetime.now(),
                    request_headers=get_request_data().get("request_headers", {}),
                    diff=history_diff,
                    subpath=dto.subpath
                )

                session.add(Histories.model_validate(history_obj))
                session.commit()

                return history_diff
            except Exception as e:
                print("[!store_entry_diff]", e)
                logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                return {}

    async def move(
            self,
            dto: core.EntityDTO,
            meta: core.Meta,
            dest_subpath: str | None,
            dest_shortname: str | None,
    ):
        """Move the file that match the criteria given, remove source folder if empty"""
        origin = await self.load(dto)

        with self.get_session() as session:
            try:
                table = self.get_table(dto)
                statement = select(table).where(table.space_name == dto.space_name)

                if table in [Roles, Permissions, Users]:
                    statement = statement.where(table.shortname == dest_shortname)
                else:
                    statement = statement.where(table.subpath == dest_subpath).where(table.shortname == dest_shortname)

                target = session.exec(statement).one_or_none()
                if target is not None:
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="create",
                            code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                            message="already exists",
                        ),
                    )

                sqlalchemy.update(table).where(table.space_name == origin.space_name) \
                    .where(table.subpath == origin.subpath) \
                    .where(table.shortname == origin.shortname) \
                    .values(subpath=dest_subpath, shortname=dest_shortname)

                session.commit()
            except Exception as e:
                print("[!move]", e)
                logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="move",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to move entry",
                    ),
                )

    def delete_empty(self, path: Path):
        pass

    async def clone(
            self,
            src_dto: core.EntityDTO,
            dest_dto: core.EntityDTO,
    ):
        pass

    async def delete(self, dto: core.EntityDTO):
        """Delete the file that match the criteria given, remove folder if empty"""
        with self.get_session() as session:
            try:
                print(f"{dto=}")
                result = await self.load(dto)
                session.delete(result)
                session.commit()
            except Exception as e:
                print("[!delete]", e)
                logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="delete",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to delete entry",
                    ),
                )

    def is_entry_exist(self, dto: core.EntityDTO) -> bool:
        with self.get_session() as session:
            table = self.get_table(dto)
            statement = select(table).where(table.space_name == dto.space_name)

            if table in [Roles, Permissions, Users]:
                statement = statement.where(table.shortname == dto.shortname)
            else:
                statement = statement.where(table.subpath == dto.subpath).where(table.shortname == dto.shortname)

            result = session.exec(statement).one_or_none()
            return False if result is None else True
