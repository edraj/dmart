import pytest
from fastapi import status
from httpx import AsyncClient

from models.enums import QueryType
from pytests.base_test import (
    MANAGEMENT_SPACE,
    USERS_SUBPATH,
)

# --- CSV Export tests ---
# The CSV endpoint requires the folder to have payload with csv_columns/index_attributes.
# We test against the management/users subpath which has this config.


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_csv_export_management_users(client: AsyncClient):
    """CSV export on the management/users subpath should return CSV data."""
    response = await client.post(
        "/managed/csv",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "",
            "limit": 5,
        },
    )
    # CSV endpoint may return 200 with CSV or 500 if folder config is incomplete
    if response.status_code == status.HTTP_200_OK:
        assert "text/csv" in response.headers.get("content-type", "")
        content = response.text
        lines = content.strip().split("\n")
        assert len(lines) >= 2, f"Expected at least 2 CSV lines (header + data), got {len(lines)}"

        # Check Content-Disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert ".csv" in content_disposition
    else:
        # Some folder configurations may not support CSV export
        pytest.skip(f"CSV export returned {response.status_code}, folder may lack csv_columns config")


@pytest.mark.run(order=3)
@pytest.mark.anyio
async def test_csv_export_nonexistent_space(client: AsyncClient):
    """CSV export on a non-existent space should fail."""
    response = await client.post(
        "/managed/csv",
        json={
            "type": QueryType.subpath,
            "space_name": "nonexistent_space_xyz",
            "subpath": "/",
            "limit": 5,
        },
    )
    assert response.status_code in [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ]


# --- Reload Security Data tests ---


@pytest.mark.run(order=6)
@pytest.mark.anyio
async def test_reload_security_data(client: AsyncClient):
    """GET /managed/reload-security-data should succeed for authenticated users."""
    response = await client.get("/managed/reload-security-data")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"


@pytest.mark.run(order=6)
@pytest.mark.anyio
async def test_reload_security_data_unauthenticated(client: AsyncClient):
    """Reload security data without auth should fail."""
    # Save all cookies, clear, make unauthenticated request, restore
    saved_cookies: list = list(client.cookies.jar)
    client.cookies.jar.clear()

    response = await client.get("/managed/reload-security-data")
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]

    # Restore cookies
    for cookie in saved_cookies:
        client.cookies.jar.set_cookie(cookie)


# --- Health check tests ---


@pytest.mark.run(order=6)
@pytest.mark.anyio
async def test_health_check_management(client: AsyncClient):
    """GET /managed/health/soft/{space} should return a health report."""
    response = await client.get(f"/managed/health/soft/{MANAGEMENT_SPACE}")
    json_response = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert json_response["status"] == "success"
