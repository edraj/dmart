import re
from builtins import Exception as PyException
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

import models.core as core
import utils.regex as regex
from models.enums import (
    DataAssetType,
    QueryType,
    RequestType,
    ResourceType,
    SortType,
    Status,
)
from utils.settings import settings

# Pattern for validating field paths used in search, sort_by, aggregation
# Only allows alphanumeric, underscore, dot (for JSON paths), hyphen, and optional @ prefix
_SAFE_FIELD_PATH = re.compile(r"^@?[a-zA-Z0-9_.\-\s,]+$")
# Blocklist of dangerous jq builtins that can leak server info
_JQ_DANGEROUS = re.compile(r"\benv\b|\$ENV\b|\binput\b|\bdebug\b|\bstderr\b|\bpath\b\(", re.IGNORECASE)


class Request(BaseModel):
    space_name: str = Field(..., pattern=regex.SPACENAME)
    request_type: RequestType
    records: list[core.Record]

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "space_name": "data",
                    "request_type": "create",
                    "records": [
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
                    ],
                }
            ]
        },
    }


class RedisReducer(BaseModel):
    reducer_name: str
    alias: str | None = None
    args: list = []

    @field_validator("reducer_name")
    @classmethod
    def validate_reducer_name(cls, v: str) -> str:
        if not _SAFE_FIELD_PATH.match(v):
            raise ValueError("reducer_name contains invalid characters")
        return v

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: str | None) -> str | None:
        if v is not None and not _SAFE_FIELD_PATH.match(v):
            raise ValueError("alias contains invalid characters")
        return v


class RedisAggregate(BaseModel):
    group_by: list[str] = []
    reducers: list[RedisReducer] = []
    load: list = []

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, v: list[str]) -> list[str]:
        for item in v:
            if not _SAFE_FIELD_PATH.match(item):
                raise ValueError(f"group_by item '{item}' contains invalid characters")
        return v


class JoinQuery(BaseModel):
    join_on: str
    alias: str
    query: Any


class Query(BaseModel):
    __pydantic_extra__ = None
    type: QueryType
    space_name: str = Field(..., pattern=regex.SPACENAME)
    subpath: str = Field(..., pattern=regex.SUBPATH)
    exact_subpath: bool = False
    filter_types: list[ResourceType] | None = None
    filter_schema_names: list[str] = ["meta"]
    filter_shortnames: list[str] | None = []
    filter_tags: list[str] | None = None
    search: str | None = Field(default=None, max_length=1024)
    from_date: datetime | None = None
    to_date: datetime | None = None
    exclude_fields: list[str] | None = None
    include_fields: list[str] | None = None
    highlight_fields: dict[str, str] = {}
    sort_by: str | None = Field(default=None, max_length=256)
    sort_type: SortType | None = None
    retrieve_json_payload: bool = False
    retrieve_attachments: bool = False
    retrieve_total: bool = True
    validate_schema: bool = True
    retrieve_lock_status: bool = False
    jq_filter: str | None = Field(default=None, max_length=1024)
    limit: int = 10
    offset: int = 0
    aggregation_data: RedisAggregate | None = None
    join: list[JoinQuery] | None = None

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str | None) -> str | None:
        if v is not None and not _SAFE_FIELD_PATH.match(v):
            raise ValueError("sort_by contains invalid characters; only alphanumeric, underscore, dot, and hyphen are allowed")
        return v

    @field_validator("jq_filter")
    @classmethod
    def validate_jq_filter(cls, v: str | None) -> str | None:
        if v is not None and _JQ_DANGEROUS.search(v):
            raise ValueError("jq_filter contains disallowed builtins (env, input, debug, stderr)")
        return v

    @field_validator("filter_shortnames")
    @classmethod
    def validate_filter_shortnames(cls, v: list[str] | None) -> list[str] | None:
        if v:
            shortname_re = re.compile(regex.SHORTNAME)
            for item in v:
                if not shortname_re.match(item):
                    raise ValueError(f"filter_shortnames item '{item}' contains invalid characters")
        return v

    # Replace -1 limit by settings.max_query_limit
    def __init__(self, **data):
        BaseModel.__init__(self, **data)
        if self.limit == -1:
            self.limit = settings.max_query_limit

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "type": "search",
                    "space_name": "acme",
                    "subpath": "/users",
                    "filter_types": [],
                    "retrieve_attachments": True,
                    "retrieve_json_payload": True,
                    "validate_schema": True,
                    "filter_shortnames": [],
                    "filter_tags": [],
                    "filter_schema_names": ["user"],
                    "search": "@first_name:joh*",
                    "limit": 10,
                    "offset": 0,
                    "exclude_fields": [],
                    "include_fields": [],
                    "from_date": None,
                    "to_date": None,
                    "sort_type": "ascending",
                    "sort_by": "created_at",
                }
            ]
        },
    }

    JoinQuery.model_rebuild()


class Error(BaseModel):
    type: str
    code: int
    message: str
    info: list[dict] | None = None


class Response(BaseModel):
    status: Status
    error: Error | None = None
    records: list[core.Record] | Any | None = None
    attributes: dict[str, Any] | None = None


class Exception(PyException):
    status_code: int
    error: Error

    def __init__(self, status_code: int, error: Error):
        super().__init__(status_code)
        self.status_code = status_code
        self.error = error


class DataAssetQuery(BaseModel):
    space_name: str = Field(..., pattern=regex.SPACENAME)
    subpath: str = Field(..., pattern=regex.SUBPATH)
    resource_type: ResourceType
    shortname: str = Field(..., pattern=regex.SHORTNAME, examples=["data_csv"])
    filter_data_assets: list[str] | None = Field(default=None, examples=["csv_chunk_3"])
    data_asset_type: DataAssetType
    query_string: str = Field(..., examples=["SELECT * FROM file"])

    @field_validator("data_asset_type")
    @classmethod
    def validate_sqlite(cls, v: DataAssetType, info: ValidationInfo):
        if v == DataAssetType.sqlite and (
            not info.data.get("filter_data_assets") or len(info.data.get("filter_data_assets", [])) != 1
        ):
            raise ValueError("filter_data_assets must include only one item in case of data_asset_type is sqlite")

        return v
