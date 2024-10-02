import pytest
from httpx import AsyncClient
from pytests.base_test import (
    DEMO_SPACE,
    DEMO_SUBPATH,
)
from pytests.feature.test_resource_and_attachment import json_entry_shortname
from fastapi import status
from models.enums import RequestType,QueryType
from utils.settings import settings


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_subpath(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={"type": QueryType.subpath, "space_name": DEMO_SPACE, "subpath": DEMO_SUBPATH},
    )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_search(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_history(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": "history",
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "",
            "filter_shortnames": [json_entry_shortname],
        },
    )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_count(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.counters,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["total"] > 0
    assert json_response["attributes"]["returned"] == 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_aggregate(client: AsyncClient) -> None:
    if settings.active_data_db == "file":
        response = await client.post(
            "/managed/query",
            json={
                "type": QueryType.aggregation,
                "space_name": DEMO_SPACE,
                "subpath": DEMO_SUBPATH,
                "search": "",
                "aggregation_data": {
                    "load": ["@resource_type", "@subpath", "@is_active"],
                    "group_by": ["@resource_type", "@subpath"],
                    "reducers": [
                        {"reducer_name": "r_count", "alias": "subpath_count"},
                        {
                            "reducer_name": "sum",
                            "alias": "active_num",
                            "args": ["is_active"],
                        },
                        {
                            "reducer_name": "random_sample",
                            "alias": "shortname_random_list",
                            "args": ["shortname", 3],
                        },
                    ],
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert json_response["status"] == "success"
        assert json_response["attributes"]["total"] > 0
        assert isinstance(json_response["records"][0]["attributes"], dict)
        assert list(json_response["records"][0]["attributes"].keys()) == [
            "resource_type",
            "subpath",
            "subpath_count",
            "active_num",
            "shortname_random_list",
        ]
    else:
        pytest.skip("Skip this test for SQL")

@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_events(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.events,
            "space_name": DEMO_SPACE,
            "subpath": "/",
            "search": "",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["total"] > 0
    assert (
        json_response["records"][0]["attributes"]["request"]
        in RequestType._value2member_map_
    )
