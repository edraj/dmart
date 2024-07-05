from main import app
from httpx import AsyncClient, ASGITransport
import pytest

# The following failed to work
from typing import AsyncGenerator
@pytest.fixture(scope="session")
async def my_client2() -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _client:  # type: ignore
         yield _client

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture()
def my_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")  # type: ignore

@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:  # type: ignore
        yield client




