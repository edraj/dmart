import pytest
from fastapi import status
from httpx import AsyncClient

from pytests.base_test import get_superman_cookie


@pytest.mark.run(order=6)
@pytest.mark.anyio
async def test_info_me(client: AsyncClient) -> None:

    client.cookies.set("auth_token", await get_superman_cookie(client))
    response = await client.get("/info/me")
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"


@pytest.mark.run(order=6)
@pytest.mark.anyio
async def test_info_manifest(client: AsyncClient) -> None:

    client.cookies.set("auth_token", await get_superman_cookie(client))
    response = await client.get("/info/manifest")
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"


@pytest.mark.run(order=6)
@pytest.mark.anyio
async def test_get_settings_should_pass(client: AsyncClient) -> None:
    client.cookies.set("auth_token", await get_superman_cookie(client))
    response = await client.get("/info/settings")
    assert response.status_code == status.HTTP_200_OK


# @pytest.mark.run(order=6)
# @pytest.mark.anyio
# async def test_in_loop_tasks(client: AsyncClient) -> None:
#     client.cookies.set("auth_token", await get_superman_cookie(client))
#     response = await client.get("/info/in-loop-tasks")
#     assert response.status_code == status.HTTP_200_OK
#     json_response = response.json()
#     assert json_response["status"] == "success"
#     assert "tasks_count" in json_response["attributes"]
#     assert isinstance(json_response["attributes"]["tasks_count"], int)
#     assert "tasks" in json_response["attributes"]
#     assert isinstance(json_response["attributes"]["tasks"], list)
#     for task in json_response["attributes"]["tasks"]:
#         assert "name" in task
#         assert "coroutine" in task
#         assert "stack" in task
