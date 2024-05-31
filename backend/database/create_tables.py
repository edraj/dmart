from typing import Dict, List
from uuid import UUID
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, create_engine, Field
from models.core import Meta, User, Locator
from models.enums import ResourceType
from utils import regex


class MetaFTable(Meta, SQLModel, table=False):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    displayname: Dict = Field(default_factory=dict, sa_type=JSON)
    description: Dict = Field(default_factory=dict, sa_type=JSON)
    tags: List[str] = Field(default_factory=dict, sa_type=JSON)
    acl: List[str] = Field(default_factory=dict, sa_type=JSON)
    payload: Dict = Field(default_factory=dict, sa_type=JSON)
    relationships: List[Dict] = Field(default_factory=dict, sa_type=JSON)


class LocatorFTable(Locator, SQLModel, table=False):
    pass


class Users(MetaFTable, User, SQLModel, table=True):
    roles: List[str] = Field(default_factory=dict, sa_type=JSON)
    groups: List[str] = Field(default_factory=dict, sa_type=JSON)


class Entries(MetaFTable, SQLModel, table=True):
    subpath: str = Field(regex=regex.SUBPATH)
    resource_type: ResourceType


class Attachments(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    parent_shortname: str = Field(regex=regex.SHORTNAME)
    shortname: str = Field(regex=regex.SHORTNAME)
    subpath: str = Field(regex=regex.SUBPATH)
    resource_type: ResourceType
    author_locator: LocatorFTable = Field(default_factory=LocatorFTable, sa_column=Column(JSON, nullable=True))
    payload: Dict = Field(default_factory=dict, sa_type=JSON)


class Histories(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    shortname: str = Field(regex=regex.SHORTNAME)
    subpath: str = Field(regex=regex.SUBPATH)
    request_headers: Dict = Field(default_factory=dict, sa_type=JSON)
    diff: Dict = Field(default_factory=dict, sa_type=JSON)


postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/dmart"
engine = create_engine(postgresql_url, echo=True)
SQLModel.metadata.create_all(engine)
