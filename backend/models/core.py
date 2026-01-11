import copy
import json
from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, TypeVar
from pydantic.types import UUID4 as UUID
from uuid import uuid4
from pydantic import Field
from datetime import datetime
import sys
from models.enums import (
    ActionType,
    ContentType,
    Language,
    NotificationPriority,
    NotificationType,
    ResourceType,
    UserType,
    ConditionType,
    PluginType,
    EventListenTime,
)
from utils.helpers import camel_case, remove_none_dict, snake_case
import utils.regex as regex
from utils.settings import settings
import utils.password_hashing as password_hashing
from hashlib import sha1 as hashlib_sha1

KeyType = TypeVar('KeyType')
def deep_update(mapping: Dict[KeyType, Any], *updating_mappings: Dict[KeyType, Any]) -> Dict[KeyType, Any]:
    updated_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                updated_mapping[k] = deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
    return updated_mapping


# class MoveModel(BaseModel):
#    resource_type: ResourceType
#    src_shortname: str = Field(regex=regex.SHORTNAME)
#    src_subpath: str = Field(regex=regex.SUBPATH)
#    dist_shortname: str = Field(default=None, regex=regex.SHORTNAME)
#    dist_subpath: str = Field(default=None, regex=regex.SUBPATH)


class Resource(BaseModel):
    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class Payload(Resource):
    content_type: ContentType
    content_sub_type: str | None = (
        None  # FIXME change to proper content type static hashmap
    )
    schema_shortname: str | None = None
    client_checksum: str | None = None
    checksum: str | None = None
    body: str | dict[str, Any] | None

    def __init__(self, **data):
        BaseModel.__init__(self, **data)

        if not self.checksum and self.body:
            sha1 = hashlib_sha1()

            if isinstance(self.body, dict):
                sha1.update(json.dumps(self.body).encode('utf-8'))
            else:
                sha1.update(self.body.encode('utf-8'))

            self.checksum = sha1.hexdigest()

    def update(
            self, payload: dict, old_body: dict | None = None, replace: bool = False
    ) -> dict | None:

        if payload.get("body", None) is None:
            return None

        if isinstance(payload["body"], dict):
            if old_body and not replace:
                separate_payload_body = dict(
                    remove_none_dict(
                        deep_update(
                            old_body,
                            payload["body"],
                        )
                    )
                )
            else:
                separate_payload_body = payload["body"]

            if "schema_shortname" in payload:
                self.schema_shortname = payload["schema_shortname"]

            return separate_payload_body

        else:
            self.body = payload["body"]
            return None


class Record(BaseModel):
    resource_type: ResourceType
    uuid: UUID | None = None
    shortname: str = Field(pattern=regex.SHORTNAME)
    subpath: str = Field(pattern=regex.SUBPATH)
    attributes: dict[str, Any]
    attachments: dict[ResourceType, list[Any]] | None = None
    retrieve_lock_status: bool = False

    def __init__(self, **data):
        BaseModel.__init__(self, **data)
        if self.subpath != "/":
            self.subpath = self.subpath.strip("/")

    def to_dict(self):
        return self.model_dump(exclude_none=True, warnings="error")

    def __eq__(self, other):
        return (
                isinstance(other, Record)
                and self.shortname == other.shortname
                and self.subpath == other.subpath
        )

    model_config = ConfigDict(
        extra= "forbid",
        json_schema_extra= { "examples": [
                {
                    "resource_type": "content",
                    "shortname": "auto",
                    "subpath": "/users",
                    "attributes": {
                        "is_active": True,
                        "slug": None,
                        "displayname": {
                            "en": "name en",
                            "ar": "name ar",
                            "ku": "name ku",
                        },
                        "description": {
                            "en": "desc en",
                            "ar": "desc ar",
                            "ku": "desc ku",
                        },
                        "tags": [],
                        "payload": {
                            "content_type": "json",
                            "schema_shortname": "user",
                            "body": {
                                "email": "myname@gmail.com",
                                "first_name": "John",
                                "language": "en",
                                "last_name": "Doo",
                                "mobile": "7999311703",
                            },
                        },
                    },
                }
            ]
        }
    )

class Translation(Resource):
    en: str | None = None
    ar: str | None = None
    ku: str | None = None


class Locator(Resource):
    uuid: UUID | None = None
    domain: str | None = None
    type: ResourceType
    space_name: str
    subpath: str
    shortname: str
    schema_shortname: str | None = None
    displayname: Translation | None = None
    description: Translation | None = None
    tags: list[str] | None = None


class Relationship(Resource):
    related_to: Locator | dict[str, Any]
    attributes: dict[str, Any]


class ACL(BaseModel):
    user_shortname: str
    allowed_actions: list[ActionType]


class Meta(Resource):
    uuid: UUID = Field(default_factory=uuid4)
    shortname: str = Field(pattern=regex.SHORTNAME)
    slug: str | None = Field(default=None, pattern=regex.SLUG)
    is_active: bool = False
    displayname: Translation | None = None
    description: Translation | None = None
    tags: list[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    owner_shortname: str
    owner_group_shortname: str | None = None
    payload: Payload | None = None
    relationships: list[Relationship] | list[dict[str, Any]] | None = None
    acl: list[ACL] | None = None
    last_checksum_history: str | None =  Field(default=None)

    model_config = ConfigDict(validate_assignment=True)

    @staticmethod
    def from_record(record: Record, owner_shortname: str):
        if record.shortname == settings.auto_uuid_rule:
            record.uuid = uuid4()
            record.shortname = str(record.uuid)[:8]
            record.attributes["uuid"] = record.uuid

        meta_class = getattr(
            sys.modules["models.core"], camel_case(record.resource_type)
        )

        if issubclass(meta_class, User) and "password" in record.attributes:
            hashed_pass = password_hashing.hash_password(record.attributes["password"])
            record.attributes["password"] = hashed_pass

        record.attributes["owner_shortname"] = owner_shortname
        record.attributes["shortname"] = record.shortname
        return meta_class(**remove_none_dict(record.attributes))

    @staticmethod
    def check_record(record: Record, owner_shortname: str):
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
            self, record: Record, old_body: dict | None = None, replace: bool = False
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
                if isinstance(self, User) and field_name == "password":
                    self.__setattr__(
                        field_name,
                        password_hashing.hash_password(record.attributes[field_name]),
                    )
                    continue

                self.__setattr__(field_name, record.attributes[field_name])

        if (
            not self.payload
            and "payload" in record.attributes
            and record.attributes["payload"] is not None
            and "content_type" in record.attributes["payload"]
        ):
            self.payload = Payload(
                content_type=ContentType(record.attributes["payload"]["content_type"]),
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
    ) -> Record:
        # Sanity check

        if self.shortname != shortname:
            raise Exception(
                f"shortname in meta({subpath}/{self.shortname}) should be same as body({subpath}/{shortname})"
            )

        record_fields = {
            "resource_type": snake_case(type(self).__name__),
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


class Space(Meta):
    root_registration_signature: str = ""
    primary_website: str = ""
    indexing_enabled: bool = False
    capture_misses: bool = False
    check_health: bool = False
    languages: list[Language] = [Language.en]
    icon: str = ""
    mirrors: list[str] = []
    hide_folders: list[str] = []
    hide_space: bool | None = None
    active_plugins: list[str] = []
    ordinal: int | None = None


class Actor(Meta):
    pass


class User(Actor):
    password: str | None = None
    email: str | None = None
    msisdn: str | None = Field(default=None, pattern=regex.MSISDN)
    locked_to_device: bool = False
    is_email_verified: bool = False
    is_msisdn_verified: bool = False
    force_password_change: bool = False
    type: UserType = UserType.web
    roles: list[str] = []
    groups: list[str] = []
    firebase_token: str | None = None
    language: Language = Language.ar
    google_id: str | None = None
    facebook_id: str | None = None
    social_avatar_url: str | None = None
    last_login: dict | None = None
    notes: str | None = None

    @staticmethod
    def invitation_url_template() -> str:
        return (
            "{url}/auth/invitation?invitation={token}&lang={lang}&user-type={user_type}"
        )


class Group(Meta):
    roles: list[str] = []  # list of entitled roles


class Attachment(Meta):
    author_locator: Locator | None = None


class DataAsset(Attachment):
    pass


class Json(Attachment):
    pass


class Jsonl(DataAsset):
    pass


class Parquet(DataAsset):
    pass


class Sqlite(DataAsset):
    pass


class Duckdb(DataAsset):
    pass


class Csv(DataAsset):
    pass


class Share(Attachment):
    pass


class Reaction(Attachment):
    pass


class Reply(Attachment):
    pass


class Comment(Attachment):
    pass


class Lock(Attachment):
    pass


class Media(Attachment):
    pass


class Alteration(Attachment):
    requested_update: dict


class Action(Resource):
    resource: Locator
    user_shortname: str
    request: ActionType
    timestamp: datetime
    attributes: dict[str, Any] | None


class History(Meta):
    timestamp: datetime
    request_headers: dict[str, Any]
    diff: dict[str, Any]


class Schema(Meta):
    pass

    # USE meta_schema TO VALIDATE ANY SCHEMA
    def __init__(self, **data):
        Meta.__init__(self, **data)
        if self.payload is not None and self.shortname != "meta_schema":
            self.payload.schema_shortname = "meta_schema"


class Content(Meta):
    pass


class Log(Meta):
    pass


class Folder(Meta):
    pass


class Permission(Meta):
    subpaths: dict[str, list[str]]  # {"space_name": ["subpath_one", "subpath_two"]}
    resource_types: list[ResourceType]
    actions: list[ActionType]
    conditions: list[ConditionType] = list()
    restricted_fields: list[str] = []
    allowed_fields_values: dict[str, list[str] | list[list[str]]] = {}
    filter_fields_values: str | None = None


class Role(Meta):
    permissions: list[str]  # list of permissions_shortnames


# class Collabolator(Resource):
#    role: str | None = ""  # a free-text role-name e.g. developer, qa, admin, ...
#    shortname: str


class Reporter(Resource):
    type: str | None = None
    name: str | None = None
    channel: str | None = None
    distributor: str | None = None
    governorate: str | None = None
    msisdn: str | None = None
    channel_address: dict | None = None


class Ticket(Meta):
    state: str
    is_open: bool = True
    reporter: Reporter | None = None
    workflow_shortname: str
    collaborators: dict[str, str] | None = None  # list[Collabolator] | None = None
    resolution_reason: str | None = None


class Post(Content):
    pass


class Event(BaseModel):
    space_name: str
    subpath: str = Field(pattern=regex.SUBPATH)
    shortname: str | None = Field(default=None, pattern=regex.SHORTNAME)
    action_type: ActionType
    resource_type: ResourceType | None = None
    schema_shortname: str | None = None
    attributes: dict = {}
    user_shortname: str


class PluginBase(ABC):
    @abstractmethod
    async def hook(self, data: Event) -> None:
        pass


class EventFilter(BaseModel):
    subpaths: list
    resource_types: list
    schema_shortnames: list
    actions: list[ActionType]


class PluginWrapper(Resource):
    shortname: str = Field(pattern=regex.SHORTNAME)
    is_active: bool = False
    filters: EventFilter | None = None
    listen_time: EventListenTime | None = None
    type: PluginType | None = None
    ordinal: int = 9999
    object: PluginBase | None = None
    dependencies: list = []


class NotificationData(Resource):
    receiver: dict
    title: Translation
    body: Translation
    image_urls: Translation | None = None
    deep_link: dict = {}
    entry_id: str | None = None


class Notification(Meta):
    """
    title: use the displayname attribute inside Meta
    description: use the description attribute inside Meta
    """

    type: NotificationType
    is_read: bool = False
    priority: NotificationPriority
    entry: Locator | None = None

    @staticmethod
    async def from_request(notification_req: dict, entry: dict = {}):
        if (
                notification_req["payload"]["schema_shortname"]
                == "admin_notification_request"
        ):
            notification_type = NotificationType.admin
        elif notification_req["payload"]["schema_shortname"] == "system_notification_request":
            notification_type = NotificationType.system
        else:
            notification_type = NotificationType.admin

        entry_locator = None
        if entry:
            entry_locator = Locator(
                space_name=entry["space_name"],
                type=ResourceType(entry["resource_type"]),
                schema_shortname=entry["payload"]["schema_shortname"],
                subpath=entry["subpath"],
                shortname=entry["shortname"],
            )

        uuid = uuid4()
        return Notification(
            uuid=uuid,
            shortname=str(uuid)[:8],
            is_active=True,
            displayname=notification_req["displayname"],
            description=notification_req["description"],
            owner_shortname=notification_req["owner_shortname"],
            type=notification_type,
            is_read=False,
            priority=notification_req["payload"]["body"]["priority"],
            entry=entry_locator,
        )
