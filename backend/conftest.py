from main import app
from httpx import AsyncClient, ASGITransport
import pytest

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

# @pytest.fixture()
# def my_client() -> AsyncClient:
#     return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")  # type: ignore

@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:  # type: ignore
        yield client




