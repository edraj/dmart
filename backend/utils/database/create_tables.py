#!/usr/bin/env -S BACKEND_ENV=config.env python3
import copy
import sys
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import JSON, LargeBinary
from sqlmodel import SQLModel, create_engine, Field, UniqueConstraint, Enum, Column
from sqlmodel._compat import SQLModelConfig
from utils.helpers import camel_case, remove_none_dict
from uuid import uuid4
from models import core
from models.enums import ResourceType, UserType, Language
from utils import regex
from utils.settings import settings
import utils.password_hashing as password_hashing


def get_model_from_sql_instance(db_record_type) :
    match db_record_type:
        case Roles.__class__:
            return core.Role
        case Permissions.__class__:
            return core.Permission
        case Users.__class__:
            return core.User
        case Spaces.__class__:
            return core.Space
        case Locks.__class__:
            return core.Lock
        case Attachments.__class__:
            return core.Attachment
        case _:
            return core.Content


class Unique(SQLModel, table=False):
    shortname: str = Field(regex=regex.SHORTNAME) # sa_type=String)
    space_name: str = Field(regex=regex.SPACENAME)
    subpath: str = Field(regex=regex.SUBPATH)
    __table_args__ = (UniqueConstraint("shortname", "space_name", "subpath"),)
    model_config = SQLModelConfig(form_attributes=True, populate_by_name=True, validate_assignment=True, use_enum_values=True, arbitrary_types_allowed=True)  # type: ignore


class Metas(Unique, table=False):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    is_active: bool = False
    slug: str | None = None
    displayname: dict | core.Translation | None = Field(default=None, sa_type=JSON)
    description: dict | core.Translation | None = Field(default=None, sa_type=JSON)
    tags: list[str] = Field(default_factory=dict, sa_type=JSON)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_shortname: str | None = None
    acl: list[core.ACL] | None = Field(default=[], sa_type=JSON)
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSON)
    relationships: list[core.Relationship] | None = Field(default=[], sa_type=JSON)

    resource_type: str = Field()
    @staticmethod
    def from_record(record: core.Record, owner_shortname: str):
        if record.shortname == settings.auto_uuid_rule:
            record.uuid = uuid4()
            record.shortname = str(record.uuid)[:8]
            record.attributes["uuid"] = record.uuid

        meta_class = getattr(
            sys.modules["models.core"], camel_case(record.resource_type)
        )

        if issubclass(meta_class, core.User) and "password" in record.attributes:
            hashed_pass = password_hashing.hash_password(record.attributes["password"])
            record.attributes["password"] = hashed_pass

        record.attributes["owner_shortname"] = owner_shortname
        record.attributes["shortname"] = record.shortname
        return meta_class(**remove_none_dict(record.attributes))

    @staticmethod
    def check_record(record: core.Record, owner_shortname: str):
        meta_class = getattr(
            sys.modules["models.core"], camel_case(record.resource_type)
        )

        meta_obj = meta_class(
            owner_shortname=owner_shortname,
            shortname=record.shortname,
            **record.attributes,
        )
        return meta_obj

    def update_from_record(
            self, record: core.Record, old_body: dict | None = None, replace: bool = False
    ) -> dict | None:
        restricted_fields = [
            "uuid",
            "shortname",
            "created_at",
            "updated_at",
            "owner_shortname",
            "payload",
            "acl",
        ]
        for field_name, _ in self.__dict__.items():
            if field_name in record.attributes and field_name not in restricted_fields:
                if isinstance(self, core.User) and field_name == "password":
                    self.__setattr__(
                        field_name,
                        password_hashing.hash_password(record.attributes[field_name]),
                    )
                    continue

                self.__setattr__(field_name, record.attributes[field_name])

        if (
                not self.payload
                and "payload" in record.attributes
                and "content_type" in record.attributes["payload"]
        ):
            self.payload = core.Payload(
                content_type=core.ContentType(record.attributes["payload"]["content_type"]),
                schema_shortname=record.attributes["payload"].get("schema_shortname"),
                body=f"{record.shortname}.json",
            )

        if self.payload and "payload" in record.attributes:
            return self.payload.update(
                payload=record.attributes["payload"], old_body=old_body, replace=replace
            )
        return None

    def to_record(
            self,
            subpath: str,
            shortname: str,
            include: list[str] = [],
    ) -> core.Record:
        # Sanity check
        if self.shortname != shortname:
            raise Exception(
                f"shortname in meta({subpath}/{self.shortname}) should be same as body({subpath}/{shortname})"
            )

        record_fields = {
            "resource_type": getattr(self, 'resource_type') if hasattr(self, 'resource_type') else get_model_from_sql_instance(self.__class__.__name__).__name__.lower(),
            "uuid": self.uuid,
            "shortname": self.shortname,
            "subpath": subpath,
        }

        attributes = {}
        for key, value in self.__dict__.items():
            if key == '_sa_instance_state':
                continue
            if (not include or key in include) and key not in record_fields:
                attributes[key] = copy.deepcopy(value)

        record_fields["attributes"] = attributes

        return core.Record(**record_fields)



class Users(Metas, table=True):
    password: str | None = None
    roles: list[str] = Field(default_factory=dict, sa_type=JSON)
    groups: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[core.ACL] | None = Field(default=[], sa_type=JSON)
    relationships: list[core.Relationship] | None = Field(default_factory=None, sa_type=JSON)
    type: UserType = Field(default=UserType.web)
    # language: Language = Field(default=Language.en)
    language: Language = Field(Column(Enum(Language)))
    email: str | None = None
    msisdn: str | None = Field(default=None, regex=regex.EXTENDED_MSISDN)
    is_email_verified: bool = False
    is_msisdn_verified: bool = False
    force_password_change: bool = True
    firebase_token: str | None = None
    google_id: str | None = None
    facebook_id: str | None = None
    social_avatar_url: str | None = None


class Roles(Metas, table=True):
    permissions: list[str] = Field(default_factory=dict, sa_type=JSON)


class Permissions(Metas, table=True):
    subpaths: dict = Field(default_factory=dict, sa_type=JSON)
    resource_types: list[str] = Field(default_factory=dict, sa_type=JSON)
    actions: list[str] = Field(default_factory=dict, sa_type=JSON)
    conditions: list[str] = Field(default_factory=dict, sa_type=JSON)
    restricted_fields: list[str] | None = Field(default_factory=None, sa_type=JSON)
    allowed_fields_values: dict | list[dict] | None = Field(default_factory=None, sa_type=JSON)


class Entries(Metas, table=True):
    # Tickets
    state: str | None = None
    is_open: bool | None = None
    reporter: dict | core.Reporter | None = Field(None, default_factory=None, sa_type=JSON)
    workflow_shortname: str | None = None
    collaborators: dict[str, str] | None = Field(None, default_factory=None, sa_type=JSON)
    resolution_reason: str | None = None


class Attachments(Metas, table=True):
    media: bytes | None = Field(None, sa_type=LargeBinary)
    body: str | None = None
    state: str | None = None


class Histories(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    request_headers: dict = Field(default_factory=dict, sa_type=JSON)
    diff: dict = Field(default_factory=dict, sa_type=JSON)
    timestamp: datetime = Field(default_factory=datetime.now)
    owner_shortname: str | None = None

    space_name: str = Field(regex=regex.SPACENAME)
    subpath: str = Field(regex=regex.SUBPATH)
    shortname: str = Field(regex=regex.SHORTNAME)

    def to_record(
        self,
        subpath: str,
        shortname: str,
        include: list[str] = [],
    ) -> core.Record:
        # Sanity check

        if self.shortname != shortname:
            raise Exception(
                f"shortname in meta({subpath}/{self.shortname}) should be same as body({subpath}/{shortname})"
            )

        record_fields = {
            "resource_type": 'history',
            "uuid": self.uuid,
            "shortname": self.shortname,
            "subpath": subpath,
        }

        attributes = {}
        for key, value in self.__dict__.items():
            if key == '_sa_instance_state':
                continue
            if (not include or key in include) and key not in record_fields:
                attributes[key] = copy.deepcopy(value)

        record_fields["attributes"] = attributes

        return core.Record(**record_fields)


class Spaces(Metas, table=True):
    root_registration_signature: str = ""
    primary_website: str = ""
    indexing_enabled: bool = False
    capture_misses: bool = False
    check_health: bool = False
    languages: list[Language] = Field(default_factory=list, sa_type=JSON)
    icon: str = ""
    mirrors: list[str] | None = Field(default_factory=None, sa_type=JSON)
    hide_folders: list[str] | None = Field(default_factory=None, sa_type=JSON)
    hide_space: bool | None = None
    active_plugins: list[str] | None = Field(default_factory=None, sa_type=JSON)
    ordinal: int | None = None


class AggregatedRecord(Unique, table=False):
    resource_type: ResourceType | None = None
    uuid: UUID | None = None
    attributes: dict[str, Any] | None = None
    attachments: dict[ResourceType, list[Any]] | None = None

    # model_config = ConfigDict(extra="allow", validate_assignment=False)


class Aggregated(Unique, table=False):
    uuid: UUID | None = None
    slug: str | None = None
    is_active: bool | None = None
    displayname: dict | core.Translation | None = Field(default_factory=None, sa_type=JSON)
    description: dict | core.Translation | None = Field(default_factory=None, sa_type=JSON)
    tags: list[str]| None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_shortname: str | None = None
    owner_group_shortname: str | None = None
    payload: dict | core.Payload | None = None
    relationships: list[core.Relationship] | None = None
    acl: list[core.ACL] | None = None

    resource_type: ResourceType | None = None
    attributes: dict[str, Any] | None = None
    attachments: dict[ResourceType, list[Any]] | None = None

    __extra__: Any | None = None

    # model_config = ConfigDict(extra="allow", validate_assignment=False)

    def to_record(
        self,
        subpath: str,
        shortname: str,
        include: list[str] = [],
        extra: dict[str, Any] | None = None,
    ) -> AggregatedRecord:
        record_fields = {
            "resource_type": getattr(self, 'resource_type') if hasattr(self, 'resource_type') else None,
            "uuid": getattr(self, 'uuid') if hasattr(self, 'uuid') else None,
            "shortname": shortname,
            "subpath": subpath,
        }

        attributes = {}

        for key, value in self.__dict__.items():
            if key == '_sa_instance_state':
                continue
            if (not include or key in include) and key not in record_fields and value is not None:
                attributes[key] = copy.deepcopy(value)

        record_fields["attributes"] = {
            **attributes,
            **(extra if extra is not None else {})
        }

        return AggregatedRecord(**record_fields)


class Locks(Unique, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    owner_shortname: str = Field(regex=regex.SHORTNAME)
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSON)


class Sessions(SQLModel, table=True):
    shortname: str = Field(regex=regex.SHORTNAME, unique=True)
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    token: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class ActiveSessions(SQLModel, table=True):
    shortname: str = Field(regex=regex.SHORTNAME, unique=True)
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    token: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class Invitations(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    invitation_token: str = Field(...)
    invitation_value: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class FailedLoginAttempts(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    shortname: str = Field(regex=regex.SHORTNAME)
    attempt_count: int = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class URLShorts(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    token_uuid: str = Field(...)
    url: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


def generate_tables():
    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    engine = create_engine(postgresql_url, echo=False)
    SQLModel.metadata.create_all(engine)

