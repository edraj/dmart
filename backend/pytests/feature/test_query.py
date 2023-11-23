import pytest
from pytests.base_test import (
    client,
    DEMO_SPACE,
    DEMO_SUBPATH,
)
from test_resource_and_attachment import json_entry_shortname
from fastapi import status
from models.enums import RequestType


@pytest.mark.run(order=3)
def test_query_subpath() -> None:
    response = client.post(
        "/managed/query",
        json={"type": "subpath", "space_name": DEMO_SPACE, "subpath": DEMO_SUBPATH},
    )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] > 0


@pytest.mark.run(order=3)
def test_query_search() -> None:
    response = client.post(
        "/managed/query",
        json={
            "type": "search",
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
def test_query_history() -> None:
    response = client.post(
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
def test_query_count() -> None:
    response = client.post(
        "/managed/query",
        json={
            "type": "counters",
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
def test_query_aggregate() -> None:
    response = client.post(
        "/managed/query",
        json={
            "type": "aggregation",
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


@pytest.mark.run(order=3)
def test_query_events() -> None:
    response = client.post(
        "/managed/query",
        json={
            "type": "events",
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
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
