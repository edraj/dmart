#!/usr/bin/env -S BACKEND_ENV=config.env python3
import copy
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, String, LargeBinary
from sqlmodel import SQLModel, create_engine, Field

from models import core
from models.enums import ResourceType, UserType, Language
from utils import regex
from utils.settings import settings


class Unique(SQLModel, table=False):
    shortname: str = Field(sa_type=String, unique=True)


class Metas(Unique, table=False):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    is_active: bool = False
    displayname: dict = Field(default={}, sa_type=JSON)
    description: dict = Field(default={}, sa_type=JSON)
    tags: list[str] = Field(default_factory=dict, sa_type=JSON)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_shortname: str | None = None
    acl: list[core.ACL] | None = Field(default=[], sa_type=JSON)
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSON)
    relationships: list[core.Relationship] | None = Field(default=[], sa_type=JSON)

    resource_type: str = Field()
    space_name: str = Field(regex=regex.SPACENAME)
    subpath: str = Field(regex=regex.SUBPATH)



class Users(Metas, table=True):
    password: str | None = None
    roles: list[str] = Field(default_factory=dict, sa_type=JSON)
    groups: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[core.ACL] | None = Field(default=[], sa_type=JSON)
    relationships: list[core.Relationship] | None = Field(default_factory=None, sa_type=JSON)
    type: UserType = Field(default=UserType.web)
    language: Language = Field(default=Language.en)

    space_name: str = Field(regex=regex.SPACENAME)


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


class Histories(Unique, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    subpath: str = Field(regex=regex.SUBPATH)
    request_headers: dict = Field(default_factory=dict, sa_type=JSON)
    diff: dict = Field(default_factory=dict, sa_type=JSON)
    timestamp: datetime = Field(default_factory=datetime.now)
    owner_shortname: str | None = None

    space_name: str = Field(regex=regex.SPACENAME)

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
    languages: list[Language] = Field(default_factory=None, sa_type=JSON)
    icon: str = ""
    mirrors: list[str] | None = Field(default_factory=None, sa_type=JSON)
    hide_folders: list[str] | None = Field(default_factory=None, sa_type=JSON)
    hide_space: bool | None = None
    active_plugins: list[str] | None = Field(default_factory=None, sa_type=JSON)
    ordinal: int | None = None


class AggregatedRecord(Unique, table=False):
    resource_type: ResourceType | None = None
    uuid: UUID | None = None
    subpath: str | None = None
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
    subpath: str | None = None
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
            "resource_type":  getattr(self, 'resource_type') if hasattr(self, 'resource_type') else None,
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
    space_name: str = Field(regex=regex.SPACENAME)
    subpath: str = Field(regex=regex.SUBPATH)
    owner_shortname: str = Field(regex=regex.SHORTNAME)
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSON)


class Sessions(Unique, SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    token: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class ActiveSessions(Unique, SQLModel, table=True):
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
