from uuid import UUID
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, create_engine, Field
from models.core import Meta, User, Locator
from models.enums import ResourceType, ActionType
from utils import regex


class ACLFTable(SQLModel, table=False):
    user_shortname: str
    allowed_actions: list[ActionType]


class MetaFTable(Meta, SQLModel, table=False):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    displayname: dict = Field(default_factory=dict, sa_type=JSON)
    description: dict = Field(default_factory=dict, sa_type=JSON)
    tags: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[ACLFTable] | None = Field(default_factory=None, sa_type=JSON)
    payload: dict = Field(default_factory=dict, sa_type=JSON)
    relationships: list[dict] | None = Field(default_factory=None, sa_type=JSON)


class LocatorFTable(Locator, SQLModel, table=False):
    pass


class Users(MetaFTable, User, SQLModel, table=True):
    roles: list[str] = Field(default_factory=dict, sa_type=JSON)
    groups: list[str] = Field(default_factory=dict, sa_type=JSON)
    acl: list[ACLFTable] | None = Field(default_factory=None, sa_column=Column(JSON, nullable=True))
    relationships: list[dict] | None = Field(default_factory=None, sa_type=JSON)


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
    payload: dict = Field(default_factory=dict, sa_type=JSON)


class Histories(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    shortname: str = Field(regex=regex.SHORTNAME)
    subpath: str = Field(regex=regex.SUBPATH)
    request_headers: dict = Field(default_factory=dict, sa_type=JSON)
    diff: dict = Field(default_factory=dict, sa_type=JSON)


def generate_tables(space_name):
    postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/"+space_name
    engine = create_engine(postgresql_url, echo=True)
    SQLModel.metadata.create_all(engine)
