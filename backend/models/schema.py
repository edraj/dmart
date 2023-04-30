import strawberry
from strawberry.scalars import JSON
from models.core import Record
from models.api import Query



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

