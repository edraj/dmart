import models.core as core
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
from builtins import Exception as PyException
from models.enums import (
    QueryType,
    ResourceType,
    SortType,
    Status,
    RequestType
)
import utils.regex as regex
from utils.settings import settings


class Request(BaseModel):
    space_name: str = Field(..., pattern=regex.SPACENAME)
    request_type: RequestType
    records: list[core.Record]

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
    branch_name: str = Field(default=settings.default_branch, pattern=regex.SHORTNAME)
    filter_types: list[ResourceType] | None = None
    filter_schema_names: list[str] = ["meta"]
    filter_shortnames: list[str] | None = [] # Field( pattern=regex.SHORTNAME, default_factory=list)
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
    jq_filter: str | None = None
    limit: int = 10
    offset: int = 0
    aggregation_data: RedisAggregate | None = None
    
    # Replace -1 limit by settings.max_query_limit
    def __init__(self, **data):
        BaseModel.__init__(self, **data)
        if self.limit == -1:
            self.limit = settings.max_query_limit 


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
