#!/usr/bin/env -S BACKEND_ENV=config.env python3
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, create_engine, Field, Enum
from models.core import Meta, User, Space, Folder
from utils import regex
from utils.settings import settings


class MetaF(Meta, SQLModel, table=False):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    displayname: Optional[dict] = Field(default={}, sa_type=JSON)
    description: dict | None = Field(default={}, sa_type=JSON)
    tags: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[dict] | None = Field(default=[], sa_type=JSON)
    payload: dict | None = Field(default_factory=None, sa_type=JSON)
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


def generate_tables():
    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    engine = create_engine(postgresql_url, echo=True)
    SQLModel.metadata.create_all(engine)
