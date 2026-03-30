# from pytests.base_test import  client
import pytest
from fastapi import status
from httpx import AsyncClient


# @pytest.mark.asyncio(scope="session")
@pytest.mark.anyio
async def test_sanity(client: AsyncClient) -> None:
    #    async with my_client as client:
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
