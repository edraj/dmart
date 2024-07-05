
from httpx import AsyncClient
from pytests.base_test import get_superman_cookie
from fastapi import status
import pytest

# @pytest.mark.asyncio(scope="session")
@pytest.mark.anyio
async def test_info_me(client: AsyncClient) -> None:
#    async with my_client as client:
    client.cookies.set("auth_token", await get_superman_cookie(client))
    response = await client.get("/info/me")
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"

# @pytest.mark.asyncio(scope="session")
@pytest.mark.anyio
async def test_info_manifest(client: AsyncClient) -> None:
 #   async with my_client as client:
        client.cookies.set("auth_token", await get_superman_cookie(client))
        response = await client.get("/info/manifest")
        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert json_response["status"] == "success"

