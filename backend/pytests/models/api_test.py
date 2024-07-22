import pytest
from pydantic import ValidationError
from models.core import Record
from models.enums import (
    DataAssetType,
    QueryType,
    ResourceType,
    SortType,
    Status,
    RequestType,
)
from utils.settings import settings
from datetime import datetime
from models.api import Request, RedisReducer, RedisAggregate, Query, Error, Response, Exception, DataAssetQuery

def test_request_model():
    record = Record(
        resource_type="content",
        shortname="auto",
        subpath="/users",
        attributes={
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
    )
    request = Request(
        space_name="data",
        request_type=RequestType.create,
        records=[record],
    )
    assert request.space_name == "data"
    assert request.request_type == RequestType.create
    assert len(request.records) == 1

    with pytest.raises(ValidationError):
        Request(
            space_name="invalid space name",
            request_type=RequestType.create,
            records=[record],
        )

def test_redis_reducer_model():
    reducer = RedisReducer(
        reducer_name="SUM",
        alias="total_sum",
        args=[1, 2, 3]
    )
    assert reducer.reducer_name == "SUM"
    assert reducer.alias == "total_sum"
    assert reducer.args == [1, 2, 3]

def test_redis_aggregate_model():
    reducer = RedisReducer(
        reducer_name="SUM",
        alias="total_sum",
        args=[1, 2, 3]
    )
    aggregate = RedisAggregate(
        group_by=["field1", "field2"],
        reducers=[reducer],
        load=["field3"]
    )
    assert aggregate.group_by == ["field1", "field2"]
    assert len(aggregate.reducers) == 1
    assert aggregate.load == ["field3"]

    # Test with default values
    default_aggregate = RedisAggregate()
    assert default_aggregate.group_by == []
    assert default_aggregate.reducers == []
    assert default_aggregate.load == []

def test_query_model():
    query = Query(
        type=QueryType.search,
        space_name="acme",
        subpath="/users",
        exact_subpath=False,
        filter_types=[ResourceType.content],
        filter_schema_names=["meta"],
        filter_shortnames=["shortname1"],
        filter_tags=["tag1"],
        search="search term",
        from_date=datetime.now(),
        to_date=datetime.now(),
        exclude_fields=["field1"],
        include_fields=["field2"],
        highlight_fields={"field3": "highlight"},
        sort_by="created_at",
        sort_type=SortType.ascending,
        retrieve_json_payload=True,
        retrieve_attachments=False,
        validate_schema=True,
        retrieve_lock_status=False,
        jq_filter="jq filter",
        limit=10,
        offset=0,
        aggregation_data=RedisAggregate()
    )
    assert query.type == QueryType.search
    assert query.space_name == "acme"
    assert query.limit == 10

    # Test -1 limit replacement
    query_with_negative_limit = Query(
        type=QueryType.search,
        space_name="acme",
        subpath="/users",
        limit=-1
    )
    assert query_with_negative_limit.limit == settings.max_query_limit

def test_error_model():
    error = Error(
        type="ValidationError",
        code=400,
        message="Invalid input",
        info=[{"field": "email", "error": "invalid email"}]
    )
    assert error.type == "ValidationError"
    assert error.code == 400
    assert error.message == "Invalid input"

    # Test without info
    error_without_info = Error(
        type="ValidationError",
        code=400,
        message="Invalid input"
    )
    assert error_without_info.info is None

def test_response_model():
    record = Record(
        resource_type="content",
        shortname="auto",
        subpath="/users",
        attributes={"is_active": True}
    )
    response = Response(
        status=Status.success,
        error=None,
        records=[record],
        attributes={"key": "value"}
    )
    assert response.status == Status.success
    assert response.records[0].shortname == "auto"

    # Test without records and attributes
    response_without_records = Response(
        status=Status.success,
        error=None
    )
    assert response_without_records.records is None
    assert response_without_records.attributes is None

def test_exception_model():
    error = Error(
        type="ValidationError",
        code=400,
        message="Invalid input"
    )
    exception = Exception(status_code=400, error=error)
    assert exception.status_code == 400
    assert exception.error.message == "Invalid input"

def test_data_asset_query_model():
    query = DataAssetQuery(
        space_name="data_space",
        subpath="/data/subpath",
        resource_type=ResourceType.content,
        shortname="data_csv",
        filter_data_assets=["csv_chunk_3"],
        data_asset_type=DataAssetType.csv,
        query_string="SELECT * FROM file"
    )
    assert query.space_name == "data_space"
    assert query.subpath == "/data/subpath"
    assert query.resource_type == ResourceType.content
    assert query.shortname == "data_csv"

    with pytest.raises(ValidationError):
        DataAssetQuery(
            space_name="data_space",
            subpath="/data/subpath",
            resource_type=ResourceType.content,
            shortname="data_csv",
            filter_data_assets=[],
            data_asset_type=DataAssetType.sqlite,
            query_string="SELECT * FROM file"
        )

    # Test with valid sqlite data_asset_type
    valid_sqlite_query = DataAssetQuery(
        space_name="data_space",
        subpath="/data/subpath",
        resource_type=ResourceType.content,
        shortname="data_csv",
        filter_data_assets=["sqlite_asset"],
        data_asset_type=DataAssetType.sqlite,
        query_string="SELECT * FROM file"
    )
    assert valid_sqlite_query.data_asset_type == DataAssetType.sqlite
    assert valid_sqlite_query.filter_data_assets == ["sqlite_asset"]
