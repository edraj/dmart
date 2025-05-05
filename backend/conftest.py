from main import app
from httpx import AsyncClient, ASGITransport
import pytest
from pytests.base_test import DEMO_SPACE, DEMO_SUBPATH


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://localhost",) as client:  # type: ignore
        yield client

@pytest.fixture
async def insert_mock_data(client: AsyncClient) -> None:
    await client.post(
        "/managed/entry",
        json={
            "space_name": DEMO_SPACE,
            "subpath": DEMO_SUBPATH,
            "payload": {
                "shortname": "john_doe_123",
                "email": "john@example.com",
                "body": {
                    "department": "Engineering"
                },
                "data_field": "example_payload_value"
            }
        }
    )

   
