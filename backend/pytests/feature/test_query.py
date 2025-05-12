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
    json_response = response.json()

    assert response.status_code == status.HTTP_200_OK
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
            "type": QueryType.history,
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
    else:
        response = await client.post(
            "/managed/query",
            json={
                "type": QueryType.aggregation,
                "space_name": DEMO_SPACE,
                "subpath": DEMO_SUBPATH,
                "search": "",
                "aggregation_data": {
                    "load": ["@resource_type", "@subpath", "@is_active"],
                    "group_by": ["@resource_type", "@subpath", "@is_active"],
                    "reducers": [
                        {"reducer_name": "r_count", "alias": "subpath_count"},
                        {
                            "reducer_name": "sum",
                            "alias": "active_num",
                            "args": ["is_active"],
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
        "active_num",
    ]

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


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_subpath(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={"type": QueryType.subpath, "space_name": settings.management_space, "subpath": settings.users_subpath, "limit":100},
    )
    json_response = response.json()
    for record in json_response.get("records", []):
        print(f"Shortname: {record['shortname']}, Owner: {record['attributes']['owner_shortname']}, Role: {record['attributes']['roles']}")

    print(json_response)
    

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] ==19


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_search(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@owner_shortname:alibaba",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 11


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_search_negative(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "-@owner_shortname:alibaba",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 8


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_search_multiple(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@owner_shortname:dmart @owner_shortname:alibaba",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 18



@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_array_query(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@roles:admin",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 16


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_payload_array(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@payload.body.skills:JavaScript",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 3


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_payload_string(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@payload.body.department:Art",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 3


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_date_single(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@created_at:2025-05-11",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 16


@pytest.mark.file_mode
@pytest.mark.anyio
async def test_query_date_range(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": settings.management_space,
            "subpath": settings.users_subpath,
            "search": "@created_at:[2023,2025]",
            "retrieve_json_payload": True,
            "limit":100
        },
    )
    json_response = response.json()
    print(json_response)

    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0
