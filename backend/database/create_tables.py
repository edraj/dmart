#!/usr/bin/env -S BACKEND_ENV=config.env python3
import copy
from datetime import datetime
from typing import Optional, Any, Self
from uuid import UUID

from pydantic import SkipValidation, ConfigDict
from sqlalchemy import Column, JSON, String, Row
from sqlmodel import SQLModel, create_engine, Field

from models import core
from models.core import Meta, User, Space, Record, Translation, Payload, Relationship, ACL
from models.enums import ResourceType
from utils import regex
from utils.settings import settings


class Unique(SQLModel, table=False):
    shortname: str = Field(sa_column=Column("shortname", String, unique=True))


class MetaF(Meta, Unique, SQLModel, table=False):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    displayname: Optional[dict] = Field(default={}, sa_type=JSON)
    description: dict | None = Field(default={}, sa_type=JSON)
    tags: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[dict] | None = Field(default=[], sa_type=JSON)
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSON)
    relationships: list[dict] | None = Field(default=[], sa_type=JSON)

    resource_type: str = Field()
    space_name: str = Field(regex=regex.SPACENAME)


class Users(MetaF, User, SQLModel, table=True):
    roles: list[str] = Field(default_factory=dict, sa_type=JSON)
    groups: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[dict] | None = Field(default=[], sa_type=JSON)
    relationships: list[dict] | None = Field(default_factory=None, sa_type=JSON)
    type: str = Field()
    language: str = Field()

    space_name: str = Field(regex=regex.SPACENAME)


class Roles(MetaF, SQLModel, table=True):
    permissions: list[str] = Field(default_factory=dict, sa_type=JSON)
    subpath: str = Field(regex=regex.SUBPATH)

    space_name: str = Field(regex=regex.SPACENAME)


class Permissions(MetaF, SQLModel, table=True):
    subpaths: dict = Field(default_factory=dict, sa_type=JSON)
    resource_types: list[str] = Field(default_factory=dict, sa_type=JSON)
    actions: list[str] = Field(default_factory=dict, sa_type=JSON)
    conditions: list[str] = Field(default_factory=dict, sa_type=JSON)
    restricted_fields: list[str] | None = Field(default_factory=None, sa_type=JSON)
    allowed_fields_values: dict | list[dict] | None = Field(default_factory=None, sa_type=JSON)
    subpath: str = Field(regex=regex.SUBPATH)

    space_name: str = Field(regex=regex.SPACENAME)


class Entries(MetaF, SQLModel, table=True):
    subpath: str = Field(regex=regex.SUBPATH)
    space_name: str = Field(regex=regex.SPACENAME)


class Attachments(MetaF, SQLModel, table=True):
    subpath: str = Field(regex=regex.SUBPATH)
    space_name: str = Field(regex=regex.SPACENAME)



class Histories(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    shortname: str = Field(regex=regex.SHORTNAME)
    subpath: str = Field(regex=regex.SUBPATH)
    request_headers: dict = Field(default_factory=dict, sa_type=JSON)
    diff: dict = Field(default_factory=dict, sa_type=JSON)
    timestamp: datetime = Field(default_factory=datetime.now)

    space_name: str = Field(regex=regex.SPACENAME)

    def to_record(
        self,
        subpath: str,
        shortname: str,
        include: list[str] = [],
    ) -> Record:
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

        return Record(**record_fields)


class Spaces(MetaF, Space, SQLModel, table=True):
    root_registration_signature: str = ""
    primary_website: str = ""
    indexing_enabled: bool = False
    capture_misses: bool = False
    check_health: bool = False
    languages: list[str] | None = Field(default_factory=None, sa_type=JSON)
    icon: str = ""
    mirrors: list[str] | None = Field(default_factory=None, sa_type=JSON)
    hide_folders: list[str] | None = Field(default_factory=None, sa_type=JSON)
    hide_space: bool | None = None
    active_plugins: list[str] | None = Field(default_factory=None, sa_type=JSON)
    branches: list[str] | None = Field(default_factory=None, sa_type=JSON)
    ordinal: int | None = None


class AggregatedRecord(SQLModel, table=False):
    resource_type: ResourceType | None = None
    uuid: UUID | None = None
    shortname: str | None = None
    subpath: str | None = None
    attributes: dict[str, Any] | None = None
    attachments: dict[ResourceType, list[Any]] | None = None

    model_config = ConfigDict(extra="allow", validate_assignment=False)


class Aggregated(SQLModel, table=False):
    uuid: UUID | None = None
    shortname: str | None = None
    slug: str | None = None
    is_active: bool | None = None
    displayname: Translation | None = None
    description: Translation | None = None
    tags: list[str]| None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_shortname: str | None = None
    owner_group_shortname: str | None = None
    payload: Payload | None = None
    relationships: list[Relationship] | None = None
    acl: list[ACL] | None = None

    resource_type: ResourceType | None = None
    subpath: str | None = None
    attributes: dict[str, Any] | None = None
    attachments: dict[ResourceType, list[Any]] | None = None

    __extra__: Any | None = None

    model_config = ConfigDict(extra="allow", validate_assignment=False)

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


def generate_tables():
    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    engine = create_engine(postgresql_url, echo=True)
    SQLModel.metadata.create_all(engine)
