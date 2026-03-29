import pytest
from fastapi import status
from httpx import AsyncClient

from models.enums import QueryType, ResourceType
from pytests.base_test import (
    DEMO_SPACE,
    DEMO_SUBPATH,
)

# --- Public Query ---
# Note: Anonymous user typically has limited or no permissions.
# Tests validate the endpoint works and returns proper responses.


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_subpath(client: AsyncClient):
    """Public query with type=subpath returns a valid response."""
    response = await client.post(
        "/public/query",
        json={
            "type": QueryType.subpath,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert "returned" in json_response["attributes"]


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_search(client: AsyncClient):
    """Public search query returns a valid response."""
    response = await client.post(
        "/public/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "",
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert "returned" in json_response["attributes"]


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_with_filter_shortnames(client: AsyncClient):
    """Public query filtered by shortname returns a valid response."""
    response = await client.post(
        "/public/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "",
            "filter_shortnames": ["json_stuff"],
            "limit": 1,
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    # Anonymous may or may not have access; just verify response format
    assert isinstance(json_response["attributes"]["returned"], int)


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_with_filter_types(client: AsyncClient):
    """Public query with filter_types returns a valid response."""
    response = await client.post(
        "/public/query",
        json={
            "type": QueryType.search,
            "space_name": DEMO_SPACE,
            "subpath": "/",
            "search": "",
            "filter_types": [ResourceType.folder],
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_counters(client: AsyncClient):
    """Public counters query returns total count with empty records."""
    response = await client.post(
        "/public/query",
        json={
            "type": QueryType.counters,
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "search": "",
        },
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert json_response["records"] == []
    assert isinstance(json_response["attributes"]["total"], int)


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_nonexistent_space(client: AsyncClient):
    """Public query on a non-existent space returns success with 0 results."""
    response = await client.post(
        "/public/query",
        json={
            "type": QueryType.search,
            "space_name": "nonexistent_space",
            "subpath": "/",
            "search": "",
        },
    )
    json_response = response.json()
    # Public query may succeed with 0 results or fail
    assert response.status_code == status.HTTP_200_OK
    assert json_response["attributes"]["returned"] == 0


# --- Public query via URL params ---


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_via_urlparams(client: AsyncClient):
    """Public query via GET URL params returns a valid response."""
    response = await client.get(
        f"/public/query/subpath/{DEMO_SPACE}/{DEMO_SUBPATH}",
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
    assert "returned" in json_response["attributes"]


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_query_via_urlparams_search(client: AsyncClient):
    """Public search query via GET URL params returns a valid response."""
    response = await client.get(
        f"/public/query/search/{DEMO_SPACE}/{DEMO_SUBPATH}",
        params={"search": ""},
    )
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"


# --- Public entry retrieval ---
# byuuid and byslug endpoints need a valid uuid/slug.
# Since json_entry_uuid is set at runtime by another test module,
# we look it up dynamically via the managed API first.


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_get_entry_by_uuid(client: AsyncClient):
    """Public retrieval by short UUID."""
    # First get a valid uuid via the authenticated managed API
    response = await client.get(f"/managed/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/json_stuff")
    if response.status_code != status.HTTP_200_OK:
        pytest.skip("Could not retrieve json_stuff entry to get UUID")
    entry_uuid = response.json()["uuid"]
    short_uuid = entry_uuid.split("-")[0]

    response = await client.get(f"/public/byuuid/{short_uuid}")
    # May succeed or return 401 depending on anonymous permissions
    if response.status_code == status.HTTP_200_OK:
        assert response.json()["uuid"] == entry_uuid
    else:
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND]


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_get_entry_by_uuid_not_found(client: AsyncClient):
    """Public retrieval by non-existent UUID should fail."""
    response = await client.get("/public/byuuid/00000000")
    assert response.status_code in [
        status.HTTP_404_NOT_FOUND,
        status.HTTP_400_BAD_REQUEST,
    ]
    assert response.json()["status"] == "failed"


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_get_entry_by_slug(client: AsyncClient):
    """Public retrieval by slug."""
    response = await client.get("/public/byslug/json_stuff_slug")
    # May succeed or return 401 depending on anonymous permissions
    if response.status_code == status.HTTP_200_OK:
        assert "uuid" in response.json()
    else:
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND]


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_get_entry_by_slug_not_found(client: AsyncClient):
    """Public retrieval by non-existent slug should fail."""
    response = await client.get("/public/byslug/nonexistent_slug_value")
    assert response.status_code in [
        status.HTTP_404_NOT_FOUND,
        status.HTTP_400_BAD_REQUEST,
    ]
    assert response.json()["status"] == "failed"


# --- Public entry meta retrieval ---


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_retrieve_entry_meta(client: AsyncClient):
    """Public entry meta retrieval -- may succeed or 401 depending on perms."""
    response = await client.get(f"/public/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/json_stuff")
    if response.status_code == status.HTTP_200_OK:
        assert response.json().get("uuid") is not None
    else:
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["status"] == "failed"


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_public_retrieve_nonexistent_entry(client: AsyncClient):
    """Public entry meta retrieval for a non-existent entry."""
    response = await client.get(f"/public/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/totally_nonexistent")
    assert response.status_code in [
        status.HTTP_404_NOT_FOUND,
        status.HTTP_401_UNAUTHORIZED,
    ]
    assert response.json()["status"] == "failed"
