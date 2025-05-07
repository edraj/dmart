import asyncio
import pytest
from httpx import AsyncClient
from pytests.base_test import (
    DEMO_SPACE,
    DEMO_SUBPATH,
)
from pytests.feature.test_resource_and_attachment import json_entry_shortname
from fastapi import status
from models.enums import RequestType,QueryType, ResourceType
from utils.settings import settings
from conftest import insert_mock_data


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

@pytest.mark.run(order=3)
@pytest.mark.anyio 
async def test_query_by_payload(client: AsyncClient, insert_mock_data) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "@payload",
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_by_shortname(client: AsyncClient, insert_mock_data) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "filter_shortnames": [json_entry_shortname],
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_by_email(client: AsyncClient, insert_mock_data) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "@john@example.com",
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_query_nested_object(client: AsyncClient, insert_mock_data) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "@Engineering",
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_save_and_query_payload_body_contents(client: AsyncClient) -> None:
    NEW_SPACE = "new_test_space"
    DEMO_SUBPATH = "/folder"
    SHORTNAME = "john_doe_123"

    await client.post(
        "managed/space",
        json={
            "space_name": NEW_SPACE,
            "request_type": RequestType.create,
            "records": [
                {
                    "resource_type": ResourceType.space,
                    "subpath": "/",
                    "shortname": NEW_SPACE,
                    "attributes": {},
                }
            ],
        },
    )

    await client.post(
        "/managed/request",
        json={
            "space_name": NEW_SPACE,
            "request_type": RequestType.create,
            "records": [
                {
                    "resource_type": ResourceType.folder,
                    "subpath": "/",
                    "shortname": DEMO_SUBPATH,
                    "attributes": {},
                }
            ],
        },
    )

    payload_data = {
        "request_type": RequestType.create,
        "space_name": NEW_SPACE,
        "records": [
            {
                "attributes": {
                    "email": "john@example.com",
                    "payload": {
                        "content_type": "json",
                        "body": {
                            "department": "Engineering",
                            "projects": [
                                {"name": "Project X", "status": "active"},
                                {"name": "Project Y", "status": "completed"},
                            ],
                            "skills": ["Python", "Django", "PostgreSQL"],
                        },
                    },
                },
                "resource_type": ResourceType.content,
                "shortname": SHORTNAME,
                "subpath": DEMO_SUBPATH,
            }
        ],
    }

    create_response = await client.post("/managed/request", json=payload_data)
    assert create_response.status_code == 200

    query_payload = {
        "space_name": NEW_SPACE,
        "subpath": DEMO_SUBPATH,
        "search": "@payload.body.department:Engineering",
        "type": QueryType.search,
        "retrieve_json_payload": True
    }

    query_response = await client.post("/managed/query", json=query_payload)
    assert query_response.status_code == 200

    response_json = query_response.json()
    assert response_json["status"] == "success"

    records = response_json["records"]
    assert records, "No records returned in query response"

    body = records[0]["attributes"]["payload"]["body"]

    assert body["department"] == "Engineering"
    assert {"name": "Project X", "status": "active"} in body["projects"]
    assert {"name": "Project Y", "status": "completed"} in body["projects"]
    for skill in ["Python", "Django", "PostgreSQL"]:
        assert skill in body["skills"]
