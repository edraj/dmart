#!/usr/bin/env -S BACKEND_ENV=config.env python3
import copy
import sys
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import LargeBinary, text, URL
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TEXT, HSTORE
from sqlmodel import SQLModel, create_engine, Field, UniqueConstraint, Enum, Column
from sqlmodel._compat import SQLModelConfig # type: ignore
from utils.helpers import camel_case, remove_none_dict
from uuid import uuid4
from models import core
from models.enums import ResourceType, UserType, Language
from utils import regex
from utils.settings import settings
import utils.password_hashing as password_hashing


metadata = SQLModel.metadata

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
    displayname: dict | core.Translation | None = Field(default=None, sa_type=JSONB)
    description: dict | core.Translation | None = Field(default=None, sa_type=JSONB)
    tags: list[str] = Field(default_factory=dict, sa_type=JSONB)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime = Field(default_factory=datetime.now, index=True)
    owner_shortname: str = Field(foreign_key="users.shortname")
    owner_group_shortname: str | None = None
    acl: list[dict[str, Any]] | list[core.ACL] | None = Field(default_factory=list, sa_type=JSONB)
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSONB)
    relationships: list[dict[str, Any]] | None = Field(default=[], sa_type=JSONB)
    last_checksum_history: str | None = Field(default=None)

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

        local_prop_list = ["uuid","resource_type","shortname","subpath"]
        return core.Record(
            resource_type= getattr(self, 'resource_type') if hasattr(self, 'resource_type') else get_model_from_sql_instance(self.__class__.__name__).__name__.lower(),
            uuid= self.uuid,
            shortname= self.shortname,
            subpath= subpath,
            attributes= {
                key: value
                for key, value in self.__dict__.items()
                if key != '_sa_instance_state' and (not include or key in include) and key not in local_prop_list
            }
        )


class Users(Metas, table=True):
    shortname: str = Field(regex=regex.SHORTNAME, unique=True)
    password: str | None = None
    roles: list[str] = Field(default_factory=dict, sa_type=JSONB)
    groups: list[str] = Field(default_factory=dict, sa_type=JSONB)
    acl: list[dict[str, Any]] | list[core.ACL] | None = Field(default_factory=list, sa_type=JSONB)
    relationships: list[dict[str, Any]] | None = Field(default_factory=None, sa_type=JSONB)
    type: UserType = Field(default=UserType.web)
    # language: Language = Field(default=Language.en)
    language: Language = Field(Column(Enum(Language)))
    email: str | None = None
    msisdn: str | None = Field(default=None, regex=regex.MSISDN)
    locked_to_device: bool = False
    is_email_verified: bool = False
    is_msisdn_verified: bool = False
    force_password_change: bool = True
    firebase_token: str | None = None
    google_id: str | None = None
    facebook_id: str | None = None
    social_avatar_url: str | None = None
    attempt_count: int | None = None
    last_login: dict | None = Field(default=None, sa_type=JSONB)
    notes: str | None = None
    last_checksum_history: str | None = Field(default=None)
    query_policies: list[str] = Field(default=[], sa_type=ARRAY(TEXT)) # type: ignore


class Roles(Metas, table=True):
    permissions: list[str] = Field(default_factory=dict, sa_type=JSONB)
    owner_shortname: str = Field(foreign_key="users.shortname")
    query_policies: list[str] = Field(default=[], sa_type=ARRAY(TEXT)) # type: ignore
    last_checksum_history: str | None = Field(default=None)


class Permissions(Metas, table=True):
    subpaths: dict = Field(default_factory=dict, sa_type=JSONB)
    resource_types: list[str] = Field(default_factory=dict, sa_type=JSONB)
    actions: list[str] = Field(default_factory=dict, sa_type=JSONB)
    conditions: list[str] = Field(default_factory=dict, sa_type=JSONB)
    restricted_fields: list[str] | None = Field(default_factory=None, sa_type=JSONB)
    allowed_fields_values: dict | list[dict] | None = Field(default_factory=None, sa_type=JSONB)
    filter_fields_values: str | None = None
    last_checksum_history: str | None = Field(default=None)
    query_policies: list[str] = Field(default=[], sa_type=ARRAY(TEXT))  # type: ignore


class Entries(Metas, table=True):
    # Tickets
    state: str | None = None
    is_open: bool | None = None
    reporter: dict | core.Reporter | None = Field(None, default_factory=None, sa_type=JSONB)
    workflow_shortname: str | None = None
    collaborators: dict[str, str] | None = Field(None, default_factory=None, sa_type=JSONB)
    resolution_reason: str | None = None
    last_checksum_history: str | None = Field(default=None)
    query_policies: list[str] = Field(default=[], sa_type=ARRAY(TEXT)) # type: ignore


class Attachments(Metas, table=True):
    media: bytes | None = Field(None, sa_type=LargeBinary)
    body: str | None = None
    state: str | None = None
    last_checksum_history: str | None = Field(default=None)


class Histories(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    request_headers: dict = Field(default_factory=dict, sa_type=JSONB)
    diff: dict = Field(default_factory=dict, sa_type=JSONB)
    timestamp: datetime = Field(default_factory=datetime.now)
    owner_shortname: str | None = None
    last_checksum_history: str | None = Field(default=None)
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
    languages: list[Language] = Field(default_factory=list, sa_type=JSONB)
    icon: str = ""
    mirrors: list[str] | None = Field(default_factory=None, sa_type=JSONB)
    hide_folders: list[str] | None = Field(default_factory=None, sa_type=JSONB)
    hide_space: bool | None = None
    active_plugins: list[str] | None = Field(default_factory=None, sa_type=JSONB)
    ordinal: int | None = None
    last_checksum_history: str | None = Field(default=None)
    query_policies: list[str] = Field(default=[], sa_type=ARRAY(TEXT)) # type: ignore


class AggregatedRecord(SQLModel, table=False):
    space_name: str | None = None
    subpath: str | None = None
    shortname: str | None = None
    resource_type: ResourceType | None = None
    uuid: UUID | None = None
    attributes: dict[str, Any] | None = None
    attachments: dict[ResourceType, list[Any]] | None = None

    # model_config = ConfigDict(extra="allow", validate_assignment=False)


class Aggregated(SQLModel, table=False):
    uuid: UUID | None = None
    slug: str | None = None
    space_name: str | None = None
    subpath: str | None = None
    shortname: str | None = None
    is_active: bool | None = None
    displayname: dict | core.Translation | None = None
    description: dict | core.Translation | None = None
    tags: list[str]| None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_shortname: str | None = None
    owner_group_shortname: str | None = None
    payload: dict | core.Payload | None = None
    relationships: list[dict[str, Any]] | None = None
    acl: list[dict[str, Any]] | None = None

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
    payload: dict | core.Payload | None = Field(default_factory=None, sa_type=JSONB)


class Sessions(SQLModel, table=True):
    shortname: str = Field(regex=regex.SHORTNAME)
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    token: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class Invitations(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    invitation_token: str = Field(...)
    invitation_value: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class URLShorts(SQLModel, table=True):
    uuid: UUID = Field(default_factory=UUID, primary_key=True)
    token_uuid: str = Field(...)
    url: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class OTP(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: dict = Field(sa_type=HSTORE)
    timestamp: datetime = Field(default_factory=datetime.now)


def generate_tables():
    postgresql_url = URL.create(
        drivername=settings.database_driver.replace('+asyncpg', '+psycopg'),
        host=settings.database_host,
        port=settings.database_port,
        username=settings.database_username,
        password=settings.database_password,
        database=settings.database_name,
    )
    engine = create_engine(postgresql_url, echo=False)

    # Enable hstore extension if it's not already enabled
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS hstore"))
        conn.commit()

    SQLModel.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS authz_mv_meta (
                id INT PRIMARY KEY,
                last_source_ts TIMESTAMPTZ,
                refreshed_at TIMESTAMPTZ
            )
        """))
        conn.execute(text("""
            INSERT INTO authz_mv_meta(id, last_source_ts, refreshed_at)
            VALUES (1, to_timestamp(0), now())
            ON CONFLICT (id) DO NOTHING
        """))

        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_roles AS
            SELECT u.shortname AS user_shortname,
                   r.shortname AS role_shortname
            FROM users u
            JOIN LATERAL jsonb_array_elements_text(u.roles) AS role_name ON TRUE
            JOIN roles r ON r.shortname = role_name
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_user_roles_unique
            ON mv_user_roles (user_shortname, role_shortname)
        """))

        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_role_permissions AS
            SELECT r.shortname AS role_shortname,
                   p.shortname AS permission_shortname
            FROM roles r
            JOIN LATERAL jsonb_array_elements_text(r.permissions) AS perm_name ON TRUE
            JOIN permissions p ON p.shortname = perm_name
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_role_permissions_unique
            ON mv_role_permissions (role_shortname, permission_shortname)
        """))
        conn.commit()

# ALERMBIC
def init_db():
    generate_tables()
    print("Tables created")
