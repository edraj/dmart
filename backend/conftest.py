from main import app
from httpx import AsyncClient, ASGITransport
import pytest

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://localhost",) as client:
        yield client
