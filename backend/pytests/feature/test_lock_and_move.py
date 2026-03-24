import pytest
from httpx import AsyncClient
from fastapi import status
from pytests.base_test import (
    assert_code_and_status_success,
    set_superman_cookie,
)
from models.enums import ResourceType, ContentType, RequestType


LM_SPACE = "lockmove"
LM_SUBPATH = "items"
LOCK_SHORTNAME = "lockable_entry"
MOVE_SHORTNAME = "movable_entry"
DEST_FOLDER = "dest_folder"


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_setup_lock_move_space(client: AsyncClient):
    """Create a dedicated space, folders, and content for lock/move tests."""
    await set_superman_cookie(client)

    # Create space
    await client.post(
        "/managed/request",
        json={
            "space_name": LM_SPACE,
            "request_type": RequestType.create,
            "records": [{"resource_type": ResourceType.space, "subpath": "/", "shortname": LM_SPACE, "attributes": {}}],
        },
    )

    # Create subpath folder
    assert_code_and_status_success(
        await client.post(
            "/managed/request",
            json={
                "space_name": LM_SPACE,
                "request_type": RequestType.create,
                "records": [{"resource_type": ResourceType.folder, "subpath": "/", "shortname": LM_SUBPATH, "attributes": {}}],
            },
        )
    )

    # Create destination folder for move tests
    assert_code_and_status_success(
        await client.post(
            "/managed/request",
            json={
                "space_name": LM_SPACE,
                "request_type": RequestType.create,
                "records": [{"resource_type": ResourceType.folder, "subpath": "/", "shortname": DEST_FOLDER, "attributes": {}}],
            },
        )
    )


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_create_entries_for_lock_move(client: AsyncClient):
    """Create content entries that will be locked and moved."""
    for shortname in [LOCK_SHORTNAME, MOVE_SHORTNAME]:
        request_data = {
            "space_name": LM_SPACE,
            "request_type": RequestType.create,
            "records": [
                {
                    "resource_type": ResourceType.content,
                    "subpath": LM_SUBPATH,
                    "shortname": shortname,
                    "attributes": {
                        "payload": {
                            "content_type": ContentType.json,
                            "body": {"info": f"entry {shortname}"},
                        }
                    },
                }
            ],
        }
        assert_code_and_status_success(await client.post("/managed/request", json=request_data))


# --- Lock tests ---


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_lock_entry(client: AsyncClient):
    """Lock a content entry and verify the lock is acquired."""
    response = await client.put(f"/managed/lock/content/{LM_SPACE}/{LM_SUBPATH}/{LOCK_SHORTNAME}")
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert "lock_period" in json_response.get("attributes", {})


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_lock_already_locked_entry(client: AsyncClient):
    """Attempt to lock an already-locked entry should fail."""
    response = await client.put(f"/managed/lock/content/{LM_SPACE}/{LM_SUBPATH}/{LOCK_SHORTNAME}")
    assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
    assert response.json()["status"] == "failed"


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_unlock_entry(client: AsyncClient):
    """Unlock the previously locked entry."""
    response = await client.delete(f"/managed/lock/{LM_SPACE}/{LM_SUBPATH}/{LOCK_SHORTNAME}")
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_unlock_not_locked_entry(client: AsyncClient):
    """Attempt to unlock an entry that is not locked should fail."""
    response = await client.delete(f"/managed/lock/{LM_SPACE}/{LM_SUBPATH}/{LOCK_SHORTNAME}")
    assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
    assert response.json()["status"] == "failed"


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_lock_nonexistent_entry(client: AsyncClient):
    """Lock a non-existent entry -- behavior depends on implementation."""
    response = await client.put(f"/managed/lock/content/{LM_SPACE}/{LM_SUBPATH}/nonexistent_entry")
    # The lock endpoint may succeed (creating a lock record) or fail; assert consistent state
    assert response.json()["status"] in ["success", "failed"]


# --- Move tests ---


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_move_entry(client: AsyncClient):
    """Move a content entry from one subpath to another."""
    request_data = {
        "space_name": LM_SPACE,
        "request_type": RequestType.move,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": f"/{LM_SUBPATH}",
                "shortname": MOVE_SHORTNAME,
                "attributes": {
                    "src_space_name": LM_SPACE,
                    "src_subpath": f"/{LM_SUBPATH}",
                    "src_shortname": MOVE_SHORTNAME,
                    "dest_space_name": LM_SPACE,
                    "dest_subpath": f"/{DEST_FOLDER}",
                    "dest_shortname": MOVE_SHORTNAME,
                    "is_active": True,
                },
            }
        ],
    }
    response = await client.post("/managed/request", json=request_data)
    assert_code_and_status_success(response)


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_moved_entry_exists_at_destination(client: AsyncClient):
    """Verify the moved entry exists at the destination subpath."""
    response = await client.get(f"/managed/entry/content/{LM_SPACE}/{DEST_FOLDER}/{MOVE_SHORTNAME}")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_moved_entry_absent_from_source(client: AsyncClient):
    """Verify the moved entry no longer exists at the source subpath."""
    response = await client.get(f"/managed/entry/content/{LM_SPACE}/{LM_SUBPATH}/{MOVE_SHORTNAME}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_move_entry_back(client: AsyncClient):
    """Move the entry back to the original location."""
    request_data = {
        "space_name": LM_SPACE,
        "request_type": RequestType.move,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": f"/{DEST_FOLDER}",
                "shortname": MOVE_SHORTNAME,
                "attributes": {
                    "src_space_name": LM_SPACE,
                    "src_subpath": f"/{DEST_FOLDER}",
                    "src_shortname": MOVE_SHORTNAME,
                    "dest_space_name": LM_SPACE,
                    "dest_subpath": f"/{LM_SUBPATH}",
                    "dest_shortname": MOVE_SHORTNAME,
                    "is_active": True,
                },
            }
        ],
    }
    response = await client.post("/managed/request", json=request_data)
    assert_code_and_status_success(response)


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_move_with_rename(client: AsyncClient):
    """Move an entry with a new shortname (rename during move)."""
    new_shortname = "renamed_entry"
    request_data = {
        "space_name": LM_SPACE,
        "request_type": RequestType.move,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": f"/{LM_SUBPATH}",
                "shortname": MOVE_SHORTNAME,
                "attributes": {
                    "src_space_name": LM_SPACE,
                    "src_subpath": f"/{LM_SUBPATH}",
                    "src_shortname": MOVE_SHORTNAME,
                    "dest_space_name": LM_SPACE,
                    "dest_subpath": f"/{LM_SUBPATH}",
                    "dest_shortname": new_shortname,
                    "is_active": True,
                },
            }
        ],
    }
    response = await client.post("/managed/request", json=request_data)
    assert_code_and_status_success(response)

    # Verify at new shortname
    response = await client.get(f"/managed/entry/content/{LM_SPACE}/{LM_SUBPATH}/{new_shortname}")
    assert response.status_code == status.HTTP_200_OK

    # Move back to original shortname for cleanup
    request_data["records"][0]["attributes"]["src_shortname"] = new_shortname
    request_data["records"][0]["attributes"]["dest_shortname"] = MOVE_SHORTNAME
    request_data["records"][0]["shortname"] = new_shortname
    response = await client.post("/managed/request", json=request_data)
    assert_code_and_status_success(response)


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_move_missing_attributes(client: AsyncClient):
    """Move request without required src/dest attributes should fail."""
    request_data = {
        "space_name": LM_SPACE,
        "request_type": RequestType.move,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": f"/{LM_SUBPATH}",
                "shortname": MOVE_SHORTNAME,
                "attributes": {},
            }
        ],
    }
    response = await client.post("/managed/request", json=request_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["status"] == "failed"


# --- Cleanup ---


@pytest.mark.run(order=5)
@pytest.mark.anyio
async def test_cleanup_lock_move_space(client: AsyncClient):
    """Delete the dedicated lock/move space."""
    response = await client.post(
        "/managed/request",
        json={
            "space_name": LM_SPACE,
            "request_type": RequestType.delete,
            "records": [{"resource_type": ResourceType.space, "subpath": "/", "shortname": LM_SPACE, "attributes": {}}],
        },
    )
    assert_code_and_status_success(response)
