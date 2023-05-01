import json
from fastapi.encoders import jsonable_encoder
import strawberry
from strawberry.scalars import JSON
from models.core import Record
from models.api import Query
from utils.helpers import pp


@strawberry.experimental.pydantic.input(
    model=Record,
    fields=[
        "resource_type",
        "uuid",
        "shortname",
        "branch_name",
        "subpath"
    ]
)
class InputRecordGQL:
    attributes: JSON

    @staticmethod
    def from_pydantic(instance: Record) -> "RecordGQL":
        return RecordGQL(**jsonable_encoder(instance))

@strawberry.experimental.pydantic.type(
    model=Record,
    fields=[
        "resource_type",
        "uuid",
        "shortname",
        "branch_name",
        "subpath"
    ]
)


class RecordGQL:
    attributes: JSON
    attachments: JSON | None = None

    @staticmethod
    def from_pydantic(instance: Record) -> "RecordGQL":
        return RecordGQL(**jsonable_encoder(instance))

@strawberry.type
class QueryResult:
    records: list[RecordGQL]
    total: int
    returned: int

@strawberry.experimental.pydantic.input(
    model=Query, 
    fields=[
        "space_name",
        "subpath",
        "exact_subpath",
        "branch_name",
        "filter_types",
        "filter_schema_names",
        "filter_shortnames",
        "filter_tags",
        "search",
        "from_date",
        "to_date",
        "exclude_fields",
        "include_fields",
        "sort_by",
        "sort_type",
        "retrieve_json_payload",
        "retrieve_attachments",
        "validate_schema",
        "jq_filter",
        "limit",
        "offset"
    ]
)
class QueryGQL:
    highlight_fields: JSON | None = None


@strawberry.type
class FailedRecord:
    record: RecordGQL
    error: str
    error_code: int


@strawberry.type
class CreateRecordSuccess:
    success_records: list[RecordGQL]
    failed_records: list[FailedRecord]


@strawberry.type
class CreateRecordFailed:
    code: int
    type: str
    message: str


ResponseGQL = strawberry.union("ResponseGQL", [
        CreateRecordSuccess,
        CreateRecordFailed
    ]
)