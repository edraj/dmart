import models.core as core
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from datetime import datetime
from typing import Any
from builtins import Exception as PyException
from models.enums import (
    DataAssetType,
    QueryType,
    ResourceType,
    SortType,
    Status,
    RequestType,
)
import utils.regex as regex
from utils.settings import settings


class Request(BaseModel):
    space_name: str = Field(..., pattern=regex.SPACENAME)
    request_type: RequestType
    records: list[core.Record]

    model_config = {
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
        }
    }


class RedisReducer(BaseModel):
    reducer_name: str
    alias: str | None = None
    args: list = []


class RedisAggregate(BaseModel):
    group_by: list[str] = []
    reducers: list[RedisReducer] = []
    load: list = []


class Query(BaseModel):
    __pydantic_extra__ = None
    type: QueryType
    space_name: str = Field(..., pattern=regex.SPACENAME)
    subpath: str = Field(..., pattern=regex.SUBPATH)
    exact_subpath: bool = False
    filter_types: list[ResourceType] | None = None
    filter_schema_names: list[str] = ["meta"]
    filter_shortnames: list[
        str
    ] | None = []  # Field( pattern=regex.SHORTNAME, default_factory=list)
    filter_tags: list[str] | None = None
    search: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    exclude_fields: list[str] | None = None
    include_fields: list[str] | None = None
    highlight_fields: dict[str, str] = {}
    sort_by: str | None = None
    sort_type: SortType | None = None
    retrieve_json_payload: bool = False
    retrieve_attachments: bool = False
    validate_schema: bool = True
    retrieve_lock_status: bool = False
    jq_filter: str | None = None
    limit: int = 10
    offset: int = 0
    aggregation_data: RedisAggregate | None = None

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
        }
    }


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
        if (
            v == DataAssetType.sqlite
            and (
                not info.data.get("filter_data_assets")
                or len(info.data.get("filter_data_assets", [])) != 1
            )
        ):
            raise ValueError(
                "filter_data_assets must include only one item in case of data_asset_type is sqlite"
            )

        return v