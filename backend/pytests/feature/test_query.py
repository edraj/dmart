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

    await client.post("/managed/space", json={
        "space_name": NEW_SPACE,
        "request_type": RequestType.create,
        "records": [{
            "resource_type": ResourceType.space,
            "subpath": "/",
            "shortname": NEW_SPACE,
            "attributes": {},
        }],
    })

    await client.post("/managed/request", json={
        "space_name": NEW_SPACE,
        "request_type": RequestType.create,
        "records": [{
            "resource_type": ResourceType.folder,
            "subpath": "/",
            "shortname": DEMO_SUBPATH,
            "attributes": {},
        }],
    })

    await client.post("/managed/request", json={
        "request_type": RequestType.create,
        "space_name": NEW_SPACE,
        "records": [
            {
                "resource_type": ResourceType.content,
                "shortname": "john_doe_123",
                "subpath": DEMO_SUBPATH,
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
            },
            {
                "resource_type": ResourceType.content,
                "shortname": "aya_123",
                "subpath": DEMO_SUBPATH,
                "attributes": {
                    "email": "aya@example.com",
                    "payload": {
                        "content_type": "json",
                        "body": {
                            "department": "Art",
                            "projects": [
                                {"name": "Design A", "status": "active"},
                                {"name": "Design B", "status": "draft"},
                            ],
                            "skills": ["Illustrator", "Photoshop", "Figma"],
                        },
                    },
                },
            },
        ]
    })

    queries = [
        "@payload.body.department:Engineering",
        "@payload.body.skills:Python",
        "@payload.body.projects.name",
    ]

    for search in queries:
        response = await client.post("/managed/query", json={
            "space_name": NEW_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": search,
            "type": QueryType.search,
            "retrieve_json_payload": True,
        })
        print(response.json())  

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert result["records"], f"No records returned for query: {search}"
        records = result["records"]  

        if search == "@payload.body.department:Engineering":
            assert any(r["attributes"]["payload"]["body"]["department"] == "Engineering" for r in records), "No record with department 'Engineering'"
        elif search == "@payload.body.skills:Python":
            assert any("Python" in r["attributes"]["payload"]["body"]["skills"] for r in records), "No record with skill 'Python'"
        elif search == "@payload.body.projects.name":
            assert any(
                any("name" in project for project in r["attributes"]["payload"]["body"].get("projects", []))
                for r in records ), "No project names found in payload"