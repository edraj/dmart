import json
import os
import sys
import time
from contextlib import contextmanager
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Type, Tuple
from uuid import uuid4
import ast
from fastapi import status
from fastapi.logger import logger
from sqlmodel import create_engine, Session, select, col, delete, update, Integer, Float, Boolean,\
    func, text
import io
from sys import modules as sys_modules
import models.api as api
from models.api import Exception as API_Exception, Error as API_Error
import models.core as core
from models.enums import QueryType, LockAction, ResourceType, SortType, ContentType
from data_adapters.sql.create_tables import (
    Entries,
    Histories,
    Permissions,
    Roles,
    Users,
    Spaces,
    Attachments,
    Locks,
    Sessions,
    Invitations,
    URLShorts,
)
from utils.helpers import (
    arr_remove_common,
    get_removed_items,
    camel_case, resolve_schema_references,
)
from utils.internal_error_code import InternalErrorCode
from utils.middleware import get_request_data
from utils.password_hashing import hash_password, verify_password
from utils.query_policies_helper import get_user_query_policies, generate_query_policies
from utils.settings import settings
from data_adapters.base_data_adapter import BaseDataAdapter, MetaChild
from data_adapters.sql.adapter_helpers import (
    set_results_from_aggregation, set_table_for_query, events_query,
    subpath_checker, parse_search_string, validate_search_range,
    sqlite_aggregate_functions, mysql_aggregate_functions,
    postgres_aggregate_functions, transform_keys_to_sql,
)
from data_adapters.helpers import get_nested_value, trans_magic_words
from jsonschema import Draft7Validator
from starlette.datastructures import UploadFile


def query_aggregation(table, query):
    aggregate_functions: list = []

    if "sqlite" in settings.database_driver:
        aggregate_functions = sqlite_aggregate_functions
    elif "mysql" in settings.database_driver:
        aggregate_functions = mysql_aggregate_functions
    elif "postgresql" in settings.database_driver:
        aggregate_functions = postgres_aggregate_functions

    statement = select(
        *[
            getattr(table, ll.replace("@", ""))
            for ll in query.aggregation_data.load
        ]
    )

    if bool(query.aggregation_data.group_by):
        statement = statement.group_by(
            *[
                table.__dict__[column]
                for column in [
                    group_by.replace("@", "")
                    for group_by in query.aggregation_data.group_by
                ]
            ]
        )

    if bool(query.aggregation_data.reducers):
        for reducer in query.aggregation_data.reducers:
            if reducer.reducer_name in aggregate_functions:
                if len(reducer.args) == 0:
                    field = "*"
                else:
                    if not hasattr(table, reducer.args[0]):
                        continue

                    field = getattr(table, reducer.args[0])

                    if field is None:
                        continue

                    if isinstance(field.type, Integer) \
                            or isinstance(field.type, Boolean):
                        field = f"{field}::int"
                    elif isinstance(field.type, Float):
                        field = f"{field}::float"
                    else:
                        field = f"{field}::text"

                statement = select(
                    getattr(func, reducer.reducer_name)(text(field)).label(reducer.alias),
                    text(f"'{reducer.alias}' AS key")
                )

    return statement


def string_to_list(input_str):
    if isinstance(input_str, list):
        return input_str
    try:
        result = ast.literal_eval(input_str)
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        return [input_str]

async def set_sql_statement_from_query(table, statement, query, is_for_count):
    try:
        if query.type == QueryType.aggregation and not is_for_count:
            statement = query_aggregation(table, query)
    except Exception as e:
        print("[!query]", e)
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="query",
                code=InternalErrorCode.SOMETHING_WRONG,
                message=str(e),
            ),
        )

    if query.space_name:
        statement = statement.where(table.space_name == query.space_name)
    if query.subpath and table is Entries:
        statement = statement.where(table.subpath == query.subpath)
    if query.search:
        if not query.search.startswith("@") and not query.search.startswith("-"):
            statement = statement.where(text(
                f"(shortname || ' ' || tags || ' ' || displayname || ' ' || description || ' ' || payload) ILIKE '%' || '{query.search}' || '%'"
            ))
        else:
            for k, v in parse_search_string(query.search, table).items():
                flag_neg = False
                if "!" in v:
                    flag_neg = True
                vv, v = validate_search_range(v)
                if isinstance(v, str):
                    v = v.replace("!", "")

                is_list = isinstance(v, list) or ("[" in v and "]" in v)
                if is_list:
                    v = string_to_list(v)

                if "->" in k:
                    if isinstance(v, str):
                        stm = f"(({k}) {'!' if flag_neg else ''}= '{v}'"
                        if "payload" in k:
                            stm += f" OR ({k.replace('>>', '>')})::jsonb @> '\"{v}\"'"
                        stm += ")"
                        statement = statement.where(text(stm))
                elif is_list and vv and v:
                    statement = statement.where(text(f"({k}) {'NOT' if flag_neg else ''} BETWEEN '{v[0]}' AND '{v[1]}'"))
                elif is_list and v:
                    in_1 = ', '.join([f"'{_v}'" for _v in v])
                    stm = f"(({k}) {'NOT' if flag_neg else ''} IN ({in_1})"
                    if "payload" in k:
                        in_2 = ', '.join([f'"{_v}"' for _v in v])
                        stm += f" OR ({k.replace('>>', '>')})::jsonb @> '[{in_2}]'"
                    stm += ")"
                    statement = statement.where(text(stm))
                elif isinstance(v, str):
                    statement = statement.where(text(f"{k} {'!' if flag_neg else ''}= '{v}'"))
                else:
                    statement = statement.where(text(f"{k} {'!' if flag_neg else ''}= {v}"))

    if query.filter_schema_names:
        if 'meta' in query.filter_schema_names:
            query.filter_schema_names.remove('meta')
        if query.filter_schema_names:
            statement = statement.where(
                text("(payload ->> 'schema_shortname') IN ({})".format(
                    ', '.join(f"'{item}'" for item in query.filter_schema_names)
                ))
            )
    if query.filter_shortnames:
        statement = statement.where(
            col(table.shortname).in_(query.filter_shortnames)
        )
    if query.filter_types:
        statement = statement.where(
            col(table.resource_type).in_(query.filter_types)
        )
    if query.filter_tags:
        statement = statement.where(
            col(table.tags).in_(query.filter_tags)
        )
    if query.from_date:
        statement = statement.where(table.created_at >= query.from_date)
    if query.to_date:
        statement = statement.where(table.created_at <= query.to_date)

    try:
        if not is_for_count:
            if query.sort_by:
                if query.sort_by.startswith('attributes.'):
                    query.sort_by = query.sort_by[11:]
                if "." in query.sort_by:
                    t = transform_keys_to_sql(query.sort_by)
                    sort_type = " DESC" if query.sort_type == SortType.descending else ""
                    t = f"CASE WHEN ({t}) ~ '^[0-9]+$' THEN ({t})::float END {sort_type}, ({t}) {sort_type}"
                    statement = statement.order_by(text(t))
                else:
                    if query.sort_type == SortType.ascending:
                        statement = statement.order_by(getattr(table, query.sort_by))
                    if query.sort_type == SortType.descending:
                        statement = statement.order_by(getattr(table, query.sort_by).desc())

    except Exception as e:
        print("[!set_sql_statement_from_query]", e)

    if not is_for_count:
        if query.offset:
            statement = statement.offset(query.offset)

        if query.limit:
            statement = statement.limit(query.limit)

    return statement

class SQLAdapter(BaseDataAdapter):
    session: Session
    engine: Any

    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        locators: list[core.Locator] = []
        total: int = 0
        match query.type:
            case api.QueryType.subpath:
                pass
                #!TODO finsih...
        return total, locators

    def folder_path(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ) -> str:
        return ""

    def metapath(self,
                 space_name: str,
                 subpath: str,
                 shortname: str,
                 class_type: Type[MetaChild],
                 schema_shortname: str | None = None,
                 ) -> tuple[Path, str]:
        return (Path(), "")

    def __init__(self):
        try:
            self.database_connection_string = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
            connection_string = f"{self.database_connection_string}/{settings.database_name}"
            self.engine = create_engine(
                connection_string, echo=False,
                max_overflow=128, pool_size=128,
            )
            # self.session = Session(self.engine)
            with self.get_session() as session:
                session.execute(text("SELECT 1")).one_or_none()
        except Exception as e:
            print("[!FATAL]", e)
            sys.exit(127)

    async def test_connection(self):
        try:
            # self.database_connection_string = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
            # connection_string = f"{self.database_connection_string}/{settings.database_name}"
            # engine = create_engine(connection_string, echo=False, pool_pre_ping=True)
            # self.session = Session(engine)
            with self.get_session() as session:
                session.execute(text("SELECT 1")).one_or_none()
        except Exception as e:
            print("[!FATAL]", e)
            sys.exit(127)

    @contextmanager
    def get_session(self):
        session = Session(self.engine)
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_table(
            self, class_type: Type[MetaChild]
    ) -> Type[Roles] | Type[Permissions] | Type[Users] | Type[Spaces] | Type[Locks] | Type[Attachments] | Type[Entries]:

        match class_type:
            case core.Role:
                return Roles
            case core.Permission:
                return Permissions
            case core.User:
                return Users
            case core.Space:
                return Spaces
            case core.Lock:
                return Locks
            case (
            core.Alteration
            | core.Media
            | core.Lock
            | core.Comment
            | core.Reply
            | core.Reaction
            | core.Json
            | core.DataAsset
            ):
                return Attachments
        return Entries

    def get_base_model(self, class_type : Type[MetaChild], data, update=None) -> Roles | Permissions | Users | Spaces | Locks | Attachments | Entries:
        match class_type:
            case core.User:
                return Users.model_validate(data, update=update)
            case core.Role:
                return Roles.model_validate(data, update=update)
            case core.Permission:
                return Permissions.model_validate(data, update=update)
            case core.Space:
                return Spaces.model_validate(data, update=update)
            case (
            core.Alteration
            | core.Media
            | core.Lock
            | core.Comment
            | core.Reply
            | core.Reaction
            | core.Json
            | core.DataAsset
            ):
                if data.get("media", None) is None:
                    data["media"] = None
                return Attachments.model_validate(data, update=update)
        return Entries.model_validate(data, update=update)

    async def get_entry_attachments(
            self,
            subpath: str,
            attachments_path: Path,
            filter_types: list | None = None,
            include_fields: list | None = None,
            filter_shortnames: list | None = None,
            retrieve_json_payload: bool = False,
    ) -> dict:
        attachments_dict: dict[str, list] = {}
        with self.get_session() as session:
            if not subpath.startswith("/"):
                subpath = f"/{subpath}"

            if str(settings.spaces_folder) in str(attachments_path):
                attachments_path = attachments_path.relative_to(settings.spaces_folder)
            space_name = attachments_path.parts[0]
            shortname = attachments_path.parts[-1]
            statement = (
                select(Attachments)
                .where(Attachments.space_name == space_name)
                .where(Attachments.subpath == f"{subpath}/{shortname}")
            )
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
                    "subpath": "/".join(attachment_json["subpath"].split("/")[:-1])#join(),
                }
                del attachment_json["resource_type"]
                del attachment_json["uuid"]
                del attachment_json["media"]
                del attachment_json["shortname"]
                del attachment_json["subpath"]
                del attachment_json["relationships"]
                del attachment_json["acl"]
                del attachment_json["space_name"]
                attachment["attributes"] = {**attachment_json}
                if attachment["resource_type"] == ResourceType.comment:
                    attachment["attributes"]["body"] = attachment["attributes"]["payload"]["body"]
                    attachment["attributes"]["state"] = attachment["attributes"]["payload"]["state"]
                    del attachment["attributes"]["payload"]
                if attachment_record.resource_type in attachments_dict:
                    attachments_dict[attachment_record.resource_type].append(attachment)
                else:
                    attachments_dict[attachment_record.resource_type] = [attachment]

        return attachments_dict

    def payload_path(
            self,
            space_name: str,
            subpath: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None, ) -> Path:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / space_name

        subpath = copy(subpath)
        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = (
            #     "." + dto.schema_shortname if dto.schema_shortname != "meta" else ""
            # )
            schema_shortname = ""
            attachment_folder = f"{parent_name}/attachments{schema_shortname}.{class_type.__name__.lower()}"
            path = path / parent_subpath / ".dm" / attachment_folder
        else:
            path = path / subpath
        return path

    async def db_load_or_none(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> Attachments | Entries | Locks | Permissions | Roles | Spaces | Users | None:
        """Load a Meta Json according to the reuqested Class type"""
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        shortname = shortname.replace("/", "")

        with self.get_session() as session:
            table = self.get_table(class_type)

            statement = select(table).where(table.space_name == space_name)
            statement = statement.where(table.shortname == shortname)

            if table in [Entries, Attachments]:
                statement = statement.where(table.subpath == subpath)

            result : Attachments | Entries | Locks | Permissions | Roles | Spaces | Users | None = session.exec(statement).one_or_none()
            if result is None:
                return None

            try:
                return result
            except Exception as e:
                print("[!load_or_none]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                return None

    async def get_entry_by_criteria(self, criteria: dict, table: Any = None) -> list[core.Record] | None:
        with self.get_session() as session:
            results: list[core.Record] = []
            if table is None:
                tables = [Entries, Users, Roles, Permissions, Spaces, Attachments]
                for _table in tables:
                    statement = select(_table)
                    for k, v in criteria.items():
                        if isinstance(v, str):
                            statement = statement.where(
                                text(f"{k}::text=:{k}")
                            ).params({k: f"{v}"})
                        else:
                            statement = statement.where(text(f"{k}=:{k}")).params({k: v})
                        _results = session.exec(statement).all()

                        if len(_results) > 0:
                            for result in _results:
                                core_model_class : core.Meta = getattr(sys.modules["models.core"], camel_case(result.resource_type))
                                results.append(
                                    core_model_class.model_validate(
                                        result.model_dump()
                                    ).to_record(result.subpath, result.shortname)
                               )

                            return results
                return None
            else:
                statement = select(table)
                for k, v in criteria.items():
                    if isinstance(v, str):
                        statement = statement.where(
                            text(f"{k}::text=:{k}")
                        ).params({k: f"{v}"})
                    else:
                        statement = statement.where(text(f"{k}=:{k}")).params({k: v})

                    _results = session.exec(statement).all()

                    if len(_results) > 0:
                        for result in _results:
                            _core_model_class: core.Meta = getattr(sys.modules["models.core"],
                                                                   camel_case(result.resource_type))
                            results.append(
                                _core_model_class.model_validate(
                                    result.model_dump()
                                ).to_record(result.subpath, result.shortname)
                            )
                        return results
                return None

    async def query(
        self, query: api.Query, user_shortname: str | None = None
    ) -> Tuple[int, list[core.Record]]:
        total : int
        results : list
        with (self.get_session() as session):
            user_query_policies = []
            if not query.subpath.startswith("/"):
                query.subpath = f"/{query.subpath}"

            table = set_table_for_query(query)

            statement = select(table)
            statement_total = select(func.count(col(table.uuid)))

            if query and query.type == QueryType.events:
                try:
                    return await events_query(query, user_shortname)
                except Exception as e:
                    print(e)
                    return 0, []
            is_fetching_spaces = False
            if (query.space_name
                    and query.type == QueryType.spaces
                    and query.space_name == "management"
                    and query.subpath == "/"):
                is_fetching_spaces = True
                statement = select(Spaces)
                statement_total = select(func.count(col(Spaces.uuid)))
            else:
                user_query_policies = await get_user_query_policies(
                    self, user_shortname if user_shortname else "anonymous", query.space_name, query.subpath
                )
                statement = await set_sql_statement_from_query(table, statement, query, False)
                statement_total = await set_sql_statement_from_query(table, statement_total, query, True)

            try:
                if query.type == QueryType.aggregation and query.aggregation_data and bool(query.aggregation_data.group_by):
                    statement_total = select(
                        func.sum(statement_total.c["count"]).label('total_count')
                    )

                total = session.exec(statement_total).one()
                total = int(total)
                if query.type == QueryType.counters:
                    return total, []

                # TODO EFFECIVENESS
                # if not query.retrieve_json_payload:
                #     cols = list(table.model_fields.keys())
                #     cols = [getattr(table, xcol) for xcol in cols if xcol not in ["payload", "media"]]
                #     statement = statement.options(load_only(*cols))
                if table not in [Attachments, Histories] and user_query_policies:
                    statement = statement.where(
                        text("EXISTS (SELECT 1 FROM unnest(query_policies) AS qp WHERE qp ILIKE ANY (:query_policies))")
                    ).params(
                        query_policies=[user_query_policy.replace('*', '%') for user_query_policy in user_query_policies]
                    )

                results = list(session.exec(statement).all())
                if is_fetching_spaces:
                    from utils.access_control import access_control
                    results = [result for result in results if await access_control.check_space_access(
                        user_shortname if user_shortname else "anonymous", result.shortname
                    )]
                if len(results) == 0:
                    return 0, []

                results = await self._set_query_final_results(query, results)

            except Exception as e:
                print("[!!query]", e)
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="query",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message=str(e),
                    ),
                )
        return total, results

    async def load_or_none(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild | None:

        result = await self.db_load_or_none(space_name, subpath, shortname, class_type, user_shortname,schema_shortname)
        if not result:
            return None

        try:
            if hasattr(result, 'payload') and result.payload and isinstance(result.payload, dict):
                if result.payload.get("body", None) is None:
                    result.payload["body"] = {}
                result.payload = core.Payload.model_validate( result.payload, strict=False)
        except Exception as e:
            print("[!load]", e)
            logger.error(f"Failed parsing an entry. Error: {e}")
        return class_type.model_validate(result.model_dump())


    async def load(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild:
        meta: MetaChild | None = await self.load_or_none(space_name, subpath, shortname, class_type, user_shortname, schema_shortname)
        if meta is None:
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available @{space_name}/{subpath}/{shortname} {class_type=} {schema_shortname=}",
                ),
            )

        return meta

    async def load_resource_payload(
            self,
            space_name: str,
            subpath: str,
            filename: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None,
    ) -> dict[str, Any] | None:
        """Load a Meta class payload file"""
        with self.get_session() as session:
            table = self.get_table(class_type)
            if not subpath.startswith("/"):
                subpath = f"/{subpath}"
            statement = select(table).where(table.space_name == space_name)

            if table in [Roles, Permissions, Users]:
                statement = statement.where(table.shortname == filename.replace('.json', ''))
            elif table in [Entries, Attachments, Histories]:
                statement = statement.where(table.subpath == subpath).where(
                    table.shortname == filename.replace('.json', '')
                )

            result = session.exec(statement).one_or_none()
            if result is None:
                return None

            var : dict = result.model_dump().get("payload", {}).get("body", {})
            return var

    async def save(
            self, space_name: str, subpath: str, meta: core.Meta
    ):
        """Save"""
        try:
            with self.get_session() as session:
                entity = {
                    **meta.model_dump(),
                    "space_name": space_name,
                    "subpath": subpath,
                }

                if meta.__class__ is core.Folder:
                    if entity["subpath"] != "/":
                        if not entity["subpath"].startswith("/"):
                            entity["subpath"] = f'/{entity["subpath"]}'
                        if entity["subpath"].endswith("/"):
                            entity["subpath"] = entity["subpath"][:-1]

                if "subpath" in entity:
                    if entity["subpath"] != "/" and entity["subpath"].endswith("/"):
                        entity["subpath"] = entity["subpath"][:-1]
                    entity["subpath"] = subpath_checker(entity["subpath"])

                try:
                    if meta.__class__ == core.Comment:
                        entity["payload"] = {
                            "content_type": ContentType.comment,
                            "body": entity['body'],
                            "state": entity['state']
                        }
                    entity['resource_type'] = meta.__class__.__name__.lower()
                    data = self.get_base_model(meta.__class__, entity)

                    if not isinstance(data, Attachments) and not isinstance(data, Histories):
                        data.query_policies = generate_query_policies(
                            space_name=space_name,
                            subpath=subpath,
                            resource_type=entity['resource_type'],
                            is_active=entity['is_active'],
                            owner_shortname=entity.get('owner_shortname', 'dmart'),
                            owner_group_shortname=entity.get('owner_group_shortname', None),
                        )

                    session.add(data)
                    session.commit()
                except Exception as e:
                    logger.error(f"Failed parsing an entry. Error: {e}")
                    return None

        except Exception as e:
            print("[!save]", e)
            logger.error(f"Failed saving an entry. Error: {e}")
            raise api.Exception(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.SOMETHING_WRONG,
                    message=f"Failed saving an entry. Error: {e}",
                ),
            )

    async def create(self, space_name: str, subpath: str, meta: core.Meta):
        result = await self.load_or_none(space_name, subpath, meta.shortname, meta.__class__)

        if result is not None:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                    message="already exists",
                ),
            )

        await self.save(space_name, subpath, meta)

    async def save_payload(
            self, space_name: str, subpath: str, meta: core.Meta, attachment
    ):
        if meta.__class__ != core.Content:
            media = await attachment.read()
            await self.update(
                space_name, subpath, meta,
                {}, {}, [],
                "", attachment_media=media
            )
        else:
            content = json.load(attachment.file)
            if meta.payload:
                meta.payload.body = content
                await self.update(
                    space_name, subpath, meta,
                    {}, {}, [],
                    ""
                )

    async def save_payload_from_json(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
    ):
        with self.get_session() as session:
            try:
                result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)
                if result is None:
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="create",
                            code=InternalErrorCode.MISSING_METADATA,
                            message="metadata is missing",
                        ),
                    )
                if meta.payload:
                    if isinstance(meta.payload.body, dict):
                        meta.payload.body = {
                            **meta.payload.body,
                            **payload_data,
                        }
                    else:
                        meta.payload.body = payload_data
                result.sqlmodel_update(meta.model_dump())

                session.add(result)
                session.commit()
            except Exception as e:
                print("[!save_payload_from_json]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="update",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to update entry",
                    ),
                )

    async def update(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            old_version_flattend: dict,
            new_version_flattend: dict,
            updated_attributes_flattend: list,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
            attachment_media: Any | None = None,
    ) -> dict:
        """Update the entry, store the difference and return it"""
        with self.get_session() as session:
            try:
                result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)
                if result is None:
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="create",
                            code=InternalErrorCode.MISSING_METADATA,
                            message="metadata is missing",
                        ),
                    )
                result.sqlmodel_update(meta.model_dump())
                if hasattr(result, "subpath") and (not result.subpath.startswith("/")):
                    result.subpath = f"/{result.subpath}"

                if isinstance(result, Attachments) and attachment_media:
                    result.media = attachment_media

                session.add(result)
                session.commit()
            except Exception as e:
                print("[!]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="update",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to update entry",
                    ),
                )

        history_diff = await self.store_entry_diff(
            space_name,
            subpath,
            meta.shortname,
            user_shortname,
            old_version_flattend,
            new_version_flattend,
            updated_attributes_flattend,
            meta.__class__,
        )
        return history_diff

    async def update_payload(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
            owner_shortname: str,
    ):
        if not meta.payload:
            meta.payload = core.Payload()
        meta.payload.body = payload_data
        await self.update(
            space_name, subpath, meta, {}, {}, [], owner_shortname
        )

    async def store_entry_diff(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            owner_shortname: str,
            old_version_flattend: dict,
            new_version_flattend: dict,
            updated_attributes_flattend: list,
            resource_type,
    ) -> dict:
        with self.get_session() as session:
            try:
                diff_keys = list(old_version_flattend.keys())
                diff_keys.extend(list(new_version_flattend.keys()))
                history_diff = {}
                for key in set(diff_keys):
                    if key in ["updated_at"]:
                        continue
                    # if key in updated_attributes_flattend:
                    old = copy(old_version_flattend.get(key, "null"))
                    new = copy(new_version_flattend.get(key, "null"))

                    if old != new:
                        if isinstance(old, list) and isinstance(new, list):
                            old, new = arr_remove_common(old, new)

                        removed = get_removed_items(list(old_version_flattend.keys()), list(new_version_flattend.keys()))

                        history_diff[key] = {
                            "old": old,
                            "new": new,
                        }
                        for r in removed:
                            history_diff[r] = {
                                "old": old_version_flattend[r],
                                "new": None,
                            }
                if not history_diff:
                    return {}

                history_obj = Histories(
                    space_name=space_name,
                    uuid=uuid4(),
                    shortname=shortname,
                    owner_shortname=owner_shortname or "__system__",
                    timestamp=datetime.now(),
                    request_headers=get_request_data().get("request_headers", {}),
                    diff=history_diff,
                    subpath=subpath,
                )

                session.add(Histories.model_validate(history_obj))
                session.commit()

                return history_diff
            except Exception as e:
                print("[!store_entry_diff]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                return {}

    async def move(
            self,
            space_name: str,
            src_subpath: str,
            src_shortname: str,
            dest_subpath: str | None,
            dest_shortname: str | None,
            meta: core.Meta,
    ):
        """Move the file that match the criteria given, remove source folder if empty"""
        if not src_subpath.startswith("/"):
            src_subpath = f"/{src_subpath}"
        if dest_subpath and not dest_subpath.startswith("/"):
            dest_subpath = f"/{dest_subpath}"

        origin = await self.db_load_or_none(space_name, src_subpath, src_shortname, meta.__class__)
        if origin is None:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                    message="already exists",
                ),
            )

        with self.get_session() as session:
            old_shortname = ""
            old_subpath = ""
            try:
                old_shortname = origin.shortname
                if hasattr(origin, 'subpath'):
                    old_subpath = origin.subpath
                table = self.get_table(meta.__class__)
                statement = select(table).where(table.space_name == space_name)

                if table in [Roles, Permissions, Users, Spaces]:
                    statement = statement.where(table.shortname == dest_shortname)
                else:
                    statement = statement.where(table.subpath == dest_subpath).where(
                        table.shortname == dest_shortname
                    )

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
                if dest_shortname:
                    origin.shortname = dest_shortname

                if hasattr(origin, 'subpath') and dest_subpath:
                    origin.subpath = dest_subpath

                session.add(origin)
                session.commit()
                try:
                    if table is Spaces:
                        session.add(
                            update(Spaces)
                            .where(col(Spaces.space_name) == space_name)
                            .values(space_name=dest_shortname))
                        session.add(
                            update(Entries)
                            .where(col(Entries.space_name) == space_name)
                            .values(space_name=dest_shortname))
                        session.add(
                            update(Attachments)
                            .where(col(Attachments.space_name) == space_name)
                            .values(space_name=dest_shortname))
                        session.commit()
                except Exception as e:
                    origin.shortname = old_shortname
                    if hasattr(origin, 'subpath'):
                        origin.subpath = old_subpath

                    session.add(origin)
                    session.commit()

                    print("[!move]", e)
                    logger.error(f"Failed parsing an entry. Error: {e}")
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="move",
                            code=InternalErrorCode.SOMETHING_WRONG,
                            message="failed to move entry",
                        ),
                    )
            except Exception as e:
                print("[!move]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
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
            src_space: str,
            dest_space: str,
            src_subpath: str,
            src_shortname: str,
            dest_subpath: str,
            dest_shortname: str,
            class_type: Type[MetaChild],
    ):
        pass

    async def is_entry_exist(self,
                       space_name: str,
                       subpath: str,
                       shortname: str,
                       resource_type: ResourceType,
                       schema_shortname: str | None = None, ) -> bool:
        with self.get_session() as session:
            resource_cls = getattr(
                sys.modules["models.core"], camel_case(resource_type)
            )

            table = self.get_table(resource_cls)
            if not subpath.startswith("/"):
                subpath = f"/{subpath}"

            statement = select(table).where(table.space_name == space_name)

            if table in [Roles, Permissions, Users]:
                statement = statement.where(table.shortname == shortname)
            elif resource_cls in [
                core.Alteration,
                core.Media,
                core.Lock,
                core.Comment,
                core.Reply,
                core.Reaction,
                core.Json,
                core.DataAsset,
            ]:
                statement = statement.where(table.subpath == subpath).where(
                    table.shortname == shortname
                )

            else:
                statement = statement.where(table.subpath == subpath).where(
                    table.shortname == shortname
                )

            result = session.exec(statement).fetchall()
            return False if len(result) == 0 else True

    async def delete(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
    ):
        """Delete the file that match the criteria given, remove folder if empty"""
        with self.get_session() as session:
            try:
                if not subpath.startswith("/"):
                    subpath = f"/{subpath}"

                result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)
                session.delete(result)
                if meta.__class__ == core.Space:
                    statement = delete(Entries).where(col(Entries.space_name) == space_name)
                    session.execute(statement)
                    statement2 = delete(Attachments).where(col(Attachments.space_name) == space_name)
                    session.execute(statement2)
                session.commit()
            except Exception as e:
                print("[!delete]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="delete",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to delete entry",
                    ),
                )

    async def lock_handler(self, space_name: str, subpath: str, shortname: str, user_shortname: str, action: LockAction) -> dict | None:
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        with self.get_session() as session:
            match action:
                case LockAction.lock:
                    statement = select(Locks).where(Locks.space_name == space_name) \
                        .where(Locks.subpath == subpath) \
                        .where(Locks.shortname == shortname)
                    result = session.exec(statement).one_or_none()
                    if result:
                        raise api.Exception(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=api.Error(
                                type="lock",
                                code=InternalErrorCode.LOCKED_ENTRY,
                                message="entry already locked already exists!",
                            )
                        )

                    lock = Locks(
                        uuid=uuid4(),
                        space_name=space_name,
                        subpath=subpath,
                        shortname=shortname,
                        owner_shortname=user_shortname,
                    )
                    session.add(lock)
                    session.commit()
                    session.refresh(lock)
                    return lock.model_dump()
                case LockAction.fetch:
                    lock_payload = (await self.load(
                        space_name=space_name,
                        subpath=subpath,
                        shortname=shortname,
                        class_type=core.Lock,
                        user_shortname=user_shortname,
                    )).model_dump()
                    return lock_payload
                case LockAction.unlock:
                    statement2 = delete(Locks) \
                        .where(col(Locks.space_name) == space_name) \
                        .where(col(Locks.subpath) == subpath) \
                        .where(col(Locks.shortname) == shortname)
                    session.execute(statement2)
                    session.commit()
        return None

    async def fetch_space(self, space_name: str) -> core.Space | None:
        try:
            return await self.load(space_name, "/", space_name, core.Space)
        except Exception as e:
            print("[!fetch_space]", e)
            return None

    async def set_user_session(self, user_shortname: str, token: str) -> bool:
        with (self.get_session() as session):
            try:
                total, last_session = await self.get_user_session(user_shortname, token)

                if (settings.max_sessions_per_user == 1 and last_session is not None) \
                    or (settings.max_sessions_per_user != 0 and total >= settings.max_sessions_per_user):
                    await self.remove_user_session(user_shortname)

                timestamp = datetime.now()
                session.add(
                    Sessions(
                        uuid=uuid4(),
                        shortname=user_shortname,
                        token=hash_password(token),
                        timestamp=timestamp,
                    )
                )
                session.commit()

                return True
            except Exception as e:
                print("[!set_sql_user_session]", e)
                return False


    async def get_user_session(self, user_shortname: str, token: str) -> Tuple[int, str | None]:
        with self.get_session() as session:
            statement = select(Sessions) \
                .where(col(Sessions.shortname) == user_shortname)

            results = session.exec(statement).all()
            if len(results) == 0:
                return 0, None

            for r in results:
                if verify_password(token, r.token):
                    if settings.session_inactivity_ttl + r.timestamp.timestamp() < time.time():
                        await self.remove_user_session(user_shortname)
                        return 0, None
                    r.timestamp = datetime.now()
                    session.add(r)
                    session.commit()
                    return len(results), token
        return len(results), None


    async def remove_user_session(self, user_shortname: str) -> bool:
        with self.get_session() as session:
            try:
                statement = select(Sessions).where(col(Sessions.shortname) == user_shortname).order_by(
                    col(Sessions.timestamp).desc()
                ).offset(settings.max_sessions_per_user)
                oldest_sessions = session.exec(statement).all()

                for oldest_session in oldest_sessions:
                    session.delete(oldest_session)
                session.commit()
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def set_invitation(self, invitation_token: str, invitation_value):
        with self.get_session() as session:
            timestamp = datetime.now()
            try:
                session.add(
                    Invitations(
                        uuid=uuid4(),
                        invitation_token=invitation_token,
                        invitation_value=invitation_value,
                        timestamp=timestamp,
                    )
                )
                session.commit()
            except Exception as e:
                print("[!set_invitation]", e)

    async def get_invitation(self, invitation_token: str) -> str | None:
        with self.get_session() as session:
            statement = select(Invitations).where(col(Invitations.invitation_token) == invitation_token)

            result = session.exec(statement).one_or_none()
            if result is None:
                return None

            user_session = Invitations.model_validate(result)

            return user_session.invitation_value

    async def delete_invitation(self, invitation_token: str) -> bool:
        with self.get_session() as session:
            try:
                statement = delete(Invitations).where(col(Invitations.invitation_token) == invitation_token)
                session.exec(statement)
                session.commit()
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def set_url_shortner(self, token_uuid: str, url: str):
        with self.get_session() as session:
            try:
                session.add(
                    URLShorts(
                        uuid=uuid4(),
                        token_uuid=token_uuid,
                        url=url,
                        timestamp=datetime.now(),
                    )
                )
                session.commit()
            except Exception as e:
                print("[!set_url_shortner]", e)

    async def get_url_shortner(self, token_uuid: str) -> str | None:
        with self.get_session() as session:
            statement = select(URLShorts).where(URLShorts.token_uuid == token_uuid)

            result = session.exec(statement).one_or_none()
            if result is None:
                return None

            url_shortner = URLShorts.model_validate(result)
            if settings.url_shorter_expires + url_shortner.timestamp.timestamp() < time.time():
                await self.delete_url_shortner(token_uuid)
                return None

            return url_shortner.url

    async def delete_url_shortner(self, token_uuid: str) -> bool:
        with self.get_session() as session:
            try:
                statement = delete(URLShorts).where(col(URLShorts.token_uuid) == token_uuid)
                session.exec(statement)
                session.commit()
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def delete_url_shortner_by_token(self, invitation_token: str) -> bool:
        with self.get_session() as session:
            try:
                statement = delete(URLShorts).where(col(URLShorts.url).ilike(f"%{invitation_token}%"))
                session.exec(statement)
                session.commit()
                return True
            except Exception as e:
                print("[!delete_url_shortner_by_token]", e)
                return False

    async def _set_query_final_results(self, query, results):
        is_aggregation = query.type == QueryType.aggregation
        not_history_event = query.type not in [QueryType.history, QueryType.events]

        for idx, item in enumerate(results):
            if is_aggregation:
                results = set_results_from_aggregation(
                    query, item, results, idx
                )
            else:
                results[idx] = item.to_record(
                    query.subpath, item.shortname
                )

            if not_history_event:
                if not query.retrieve_json_payload:
                    attrb = results[idx].attributes
                    if (
                        attrb
                        and attrb.get("payload", {})
                        and attrb.get("payload", {}).get("body", False)
                    ):
                        attrb["payload"]["body"] = None

                if query.retrieve_attachments:
                    results[idx].attachments = await self.get_entry_attachments(
                        query.subpath,
                        Path(f"{query.space_name}/{results[idx].shortname}"),
                        retrieve_json_payload=True,
                    )

        return results

    async def clear_failed_password_attempts(self, user_shortname: str) -> bool:
        with self.get_session() as session:
            try:
                statement = select(Users).where(Users.shortname == user_shortname)
                result = session.exec(statement).one_or_none()
                if result is None:
                    return False
                result.attempt_count = 0
                session.add(result)
                session.commit()
                return True
            except Exception as e:
                print("[!clear_failed_password_attempts]", e)
                return False

    async def get_failed_password_attempt_count(self, user_shortname: str) -> int:
        with self.get_session() as session:
            statement = select(Users).where(col(Users.shortname) == user_shortname)

            result = session.exec(statement).one_or_none()
            if result is None:
                return 0

            failed_login_attempt = Users.model_validate(result)
            return 0 if failed_login_attempt.attempt_count is None else failed_login_attempt.attempt_count

    async def set_failed_password_attempt_count(self, user_shortname: str, attempt_count: int) -> bool:
        with self.get_session() as session:
            try:
                statement = select(Users).where(col(Users.shortname) == user_shortname)
                result = session.exec(statement).one_or_none()
                if result is None:
                    return False
                result.attempt_count = attempt_count
                session.add(result)
                session.commit()
                return True
            except Exception as e:
                print("[!set_failed_password_attempt_count]", e)
                return False

    async def get_spaces(self) -> dict:
        with self.get_session() as session:
            statement = select(Spaces)
            results = session.exec(statement).all()
            spaces = {}
            for idx, item in enumerate(results):
                space = Spaces.model_validate(item)
                spaces[space.shortname] = space.model_dump()
            return spaces

    async def get_media_attachments(self, space_name: str, subpath: str, shortname: str) -> io.BytesIO | None:
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        with self.get_session() as session:
            statement = select(Attachments.media) \
                .where(Attachments.space_name == space_name) \
                .where(Attachments.subpath == subpath) \
                .where(Attachments.shortname == shortname)

            result = session.exec(statement).one_or_none()
            if result:
                return io.BytesIO(result)
        return None

    async def validate_uniqueness(
        self, space_name: str, record: core.Record, action: str = api.RequestType.create, user_shortname=None
    ) -> bool:
        """
        Get list of unique fields from entry's folder meta data
        ensure that each sub-list in the list is unique across all entries
        """
        parent_subpath, folder_shortname = os.path.split(record.subpath)
        folder_meta = None
        try:
            folder_meta = await self.load(space_name, parent_subpath, folder_shortname, core.Folder)
        except Exception:
            folder_meta = None

        if folder_meta is None or folder_meta.payload is None or not isinstance(folder_meta.payload.body,
                                                                            dict) or not isinstance(
                folder_meta.payload.body.get("unique_fields", None), list):  # type: ignore
            return True

        current_user = None
        if action is api.RequestType.update and record.resource_type is ResourceType.user:
            current_user = await self.load(space_name, record.subpath, record.shortname, core.User)


        for compound in folder_meta.payload.body["unique_fields"]:  # type: ignore
            query_string = ""
            for composite_unique_key in compound:
                value = get_nested_value(record.attributes, composite_unique_key)
                if value is None or value == "":
                    continue
                if current_user is not None and hasattr(current_user,composite_unique_key) \
                        and getattr(current_user,composite_unique_key) == value:
                    continue

                query_string += f"@{composite_unique_key}:{value} "

            if query_string == "":
                continue

            q = api.Query(
                space_name=space_name,
                subpath=record.subpath,
                type=QueryType.subpath,
                search=query_string
            )
            owner = record.attributes.get("owner_shortname", None) if user_shortname is None else user_shortname
            total, _ = await self.query(q, owner)

            if total != 0:
                raise API_Exception(
                    status.HTTP_400_BAD_REQUEST,
                    API_Error(
                        type="request",
                        code=InternalErrorCode.DATA_SHOULD_BE_UNIQUE,
                        message=f"Entry properties should be unique: {query_string}",
                    ),
                )
        return True

    async def validate_payload_with_schema(
            self,
            payload_data: UploadFile | dict,
            space_name: str,
            schema_shortname: str,
    ):
        if not isinstance(payload_data, (dict, UploadFile)):
            raise API_Exception(
                status.HTTP_400_BAD_REQUEST,
                API_Error(
                    type="request",
                    code=InternalErrorCode.INVALID_DATA,
                    message="Invalid payload.body",
                ),
            )

        if schema_shortname in ["folder_rendering", "meta_schema"]:
            space_name = "management"
        schema = await self.load(space_name, "/schema", schema_shortname, core.Schema)
        if schema.payload:
            schema = schema.payload.model_dump()['body']

        if not isinstance(payload_data, dict):
            data = json.load(payload_data.file)
            payload_data.file.seek(0)
        else:
            data = payload_data

        Draft7Validator(schema).validate(data)  # type: ignore

    async def get_schema(self, space_name: str, schema_shortname: str, owner_shortname: str) -> dict:
        schema_content = await self.load(
            space_name=space_name,
            subpath="/schema",
            shortname=schema_shortname,
            class_type=core.Schema,
            user_shortname=owner_shortname,
        )

        if schema_content and schema_content.payload and isinstance(schema_content.payload.body, dict):
            return resolve_schema_references(schema_content.payload.body)

        return {}

    async def check_uniqueness(self, unique_fields, search_str, redis_escape_chars) -> dict:
        for key, value in unique_fields.items():
            if value is None:
                continue
            if key == "email_unescaped":
                key = "email"

            result = await self.get_entry_by_criteria({key: value}, Users)

            if result is not None:
                return {"unique": False, "field": key}

        return {"unique": True}

    async def get_role_permissions(self, role: core.Role) -> list[core.Permission]:
        role_records = await self.load_or_none(
            settings.management_space, 'roles', role.shortname, core.Role
        )

        if role_records is None:
            return []

        role_permissions: list[core.Permission] = []

        for permission in role_records.permissions:
            permission_record = await self.load_or_none(
                settings.management_space, 'permissions', permission, core.Permission
            )
            if permission_record is None:
                continue
            role_permissions.append(permission_record)

        return role_permissions

    async def get_user_roles(self, user_shortname: str) -> dict[str, core.Role]:
        try:
            user = await self.load_or_none(
                settings.management_space, settings.users_subpath, user_shortname, core.User
            )

            if user is None:
                return {}

            user_roles: dict[str, core.Role] = {}
            for role in user.roles:
                role_record = await self.load_or_none(
                    settings.management_space, 'roles', role, core.Role
                )
                if role_record is None:
                    continue

                user_roles[role] = role_record
            return user_roles
        except Exception as e:
            print(f"Error: {e}")
            return {}

    async def load_user_meta(self, user_shortname: str) -> Any:
        user = await self.load(
            space_name=settings.management_space,
            shortname=user_shortname,
            subpath="users",
            class_type=core.User,
            user_shortname=user_shortname,
        )

        return user

    async def generate_user_permissions(self, user_shortname: str) -> dict:
        user_permissions: dict = {}

        user_roles = await self.get_user_roles(user_shortname)

        for _, role in user_roles.items():
            role_permissions = await self.get_role_permissions(role)
            permission_world_record = await self.load_or_none(settings.management_space, 'permissions', "world",
                                                            core.Permission)
            if permission_world_record:
                role_permissions.append(permission_world_record)

            for permission in role_permissions:
                for space_name, permission_subpaths in permission.subpaths.items():
                    for permission_subpath in permission_subpaths:
                        permission_subpath = trans_magic_words(permission_subpath, user_shortname)
                        for permission_resource_types in permission.resource_types:
                            actions = set(permission.actions)
                            conditions = set(permission.conditions)
                            if (
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                    in user_permissions
                            ):
                                old_perm = user_permissions[
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                ]

                                if isinstance(actions, list):
                                    actions = set(actions)
                                actions |= set(old_perm["allowed_actions"])

                                if isinstance(conditions, list):
                                    conditions = set(conditions)
                                conditions |= set(old_perm["conditions"])

                            user_permissions[
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                            ] = {
                                "allowed_actions": list(actions),
                                "conditions": list(conditions),
                                "restricted_fields": permission.restricted_fields,
                                "allowed_fields_values": permission.allowed_fields_values
                            }
        return user_permissions

    async def get_user_permissions(self, user_shortname: str) -> dict:
        return await self.generate_user_permissions(user_shortname)

    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        _user = await self.get_entry_by_criteria(
            {key: value},
            Users
        )
        if _user is None or len(_user) == 0:
            return None
        return str(_user[0].shortname)

    async def get_payload_from_event(self, event) -> dict:
        notification_request_meta = await self.load(
            event.space_name,
            event.subpath,
            event.shortname,
            getattr(sys_modules["models.core"], camel_case(event.resource_type)),
            event.user_shortname,
        )
        return notification_request_meta.payload.body # type: ignore

    async def get_user_roles_from_groups(self, user_meta: core.User) -> list:
        return []

    async def drop_index(self, space_name):
        pass

    async def initialize_spaces(self) -> None:
        pass

    async def create_user_premission_index(self) -> None:
        pass

    async def store_modules_to_redis(self, roles, groups, permissions) -> None:
        pass

    async def delete_user_permissions_map_in_redis(self) -> None:
        pass

    async def internal_save_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload: dict | None = None
    ):
        await self.save(
            space_name=space_name,
            subpath=subpath,
            meta=meta,
        )

    async def internal_sys_update_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            updates: dict,
            sync_redis: bool = True,
            payload_dict: dict[str, Any] = {},
    ):
        meta.updated_at = datetime.now()
        meta_updated = False
        payload_updated = False

        if not payload_dict:
            try:
                body = str(meta.payload.body) if meta and meta.payload else ""
                mydict = await self.load_resource_payload(
                    space_name, subpath, body, core.Content
                )
                payload_dict = mydict if mydict else {}
            except Exception:
                pass

        restricted_fields = [
            "uuid",
            "shortname",
            "created_at",
            "updated_at",
            "owner_shortname",
            "payload",
        ]
        old_version_flattend = {**meta.model_dump()}
        for key, value in updates.items():
            if key in restricted_fields:
                continue

            if key in meta.model_fields.keys():
                meta_updated = True
                meta.__setattr__(key, value)
            elif payload_dict:
                payload_dict[key] = value
                payload_updated = True

        if meta_updated:
            await self.update(
                space_name,
                subpath,
                meta,
                old_version_flattend,
                {**meta.model_dump()},
                list(updates.keys()),
                meta.shortname
            )
        if payload_updated and meta.payload and meta.payload.schema_shortname:
            await self.validate_payload_with_schema(
                payload_dict, space_name, meta.payload.schema_shortname
            )
            await self.save_payload_from_json(
                space_name, subpath, meta, payload_dict
            )

    async def get_entry_by_var(
            self,
            key: str,
            val: str,
            logged_in_user,
            retrieve_json_payload: bool = False,
            retrieve_attachments: bool = False,
            retrieve_lock_status: bool = False,
    ) -> core.Record:
        _result = await self.get_entry_by_criteria({key: val})

        if _result is None or len(_result) == 0:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
                ),
            )

        return _result[0]

    async def delete_space(self, space_name, record, owner_shortname):
        resource_obj = core.Meta.from_record(
            record=record, owner_shortname=owner_shortname
        )
        await self.delete(space_name, record.subpath, resource_obj, owner_shortname)
        os.system(f"rm -r {settings.spaces_folder}/{space_name}")

    async def get_last_updated_entry(
            self,
            space_name: str,
            schema_names: list,
            retrieve_json_payload: bool,
            logged_in_user: str,
    ):
        pass

    async def get_group_users(self, group_name: str):
        return []

    async def is_user_verified(self, user_shortname: str | None, identifier: str | None) -> bool:
        return True
