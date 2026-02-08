import pytest
from httpx import AsyncClient
from fastapi import status
from utils.internal_error_code import InternalErrorCode
from pytests.base_test import (
    assert_code_and_status_success,
    assert_resource_created,
    set_superman_cookie,
    MANAGEMENT_SPACE,
    USERS_SUBPATH,
    superman
)
from models.api import Query
from models.enums import QueryType, ResourceType
from fastapi import status
from utils.internal_error_code import InternalErrorCode


new_user_data = {
    "shortname": "test_user_100100",
    "msisdn": "7777778220",
    "email": "test_user_100100@mymail.com",
}


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_user_does_not_exist(client: AsyncClient):
    await set_superman_cookie(client)
    response = await client.get("/user/check-existing", params=new_user_data)
    assert_code_and_status_success(response)
    assert response.json()["attributes"]["unique"] is True

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_request_email_otp(client: AsyncClient):
    request_body = {
        "email": new_user_data["email"]
    }
    response = await client.post("/user/otp-request", json=request_body)
    json_response = response.json()
    if response.status_code == status.HTTP_200_OK:
        assert json_response.get("status") == "success"
    elif response.status_code == status.HTTP_403_FORBIDDEN:
        assert json_response.get("error", {}).get("code") == InternalErrorCode.OTP_RESEND_BLOCKED

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_request_msisdn_otp(client: AsyncClient):
    request_body = {
        "msisdn": new_user_data["msisdn"]
    }
    response = await client.post("/user/otp-request", json=request_body)
    json_response = response.json()
    if response.status_code == status.HTTP_200_OK:
        assert json_response.get("status") == "success"
    elif response.status_code == status.HTTP_403_FORBIDDEN:
        assert json_response.get("error", {}).get("code") == InternalErrorCode.OTP_RESEND_BLOCKED
    
@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_create_user(client: AsyncClient):
    request_body = {
        "resource_type": ResourceType.user,
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            "password": "Test1234",
            "email": new_user_data["email"],
            "email_otp": "123456",
            "msisdn": new_user_data["msisdn"],
            "msisdn_otp": "123456"
        },
    }

    response = await client.post("/user/create", json=request_body)
    assert_code_and_status_success(response)

    await assert_resource_created(
        client,
        query=Query(
            type=QueryType.search,
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            filter_shortnames=[new_user_data["shortname"]],
            filter_types=[ResourceType.user],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=new_user_data["shortname"],
        res_subpath=USERS_SUBPATH,
        res_attributes={},
    )
    
@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_the_new_user(client: AsyncClient):
    response = await client.post(
        "/user/login",
        json={
            "msisdn": new_user_data["msisdn"],
            "password": "Test1234",
        },
    )
    assert_code_and_status_success(response)
    response = await client.post(
        "/user/login",
        json={
            "email": new_user_data["email"],
            "password": "Test1234",
        },
    )
    assert_code_and_status_success(response)
    response = await client.post(
        "/user/login",
        json={
            "shortname": new_user_data["shortname"],
            "password": "Test1234",
        },
    )
    assert_code_and_status_success(response)
    client.cookies.set("auth_token", response.cookies["auth_token"])


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_get_profile(client: AsyncClient) -> None:
    response = await client.get("/user/profile")
    assert_code_and_status_success(response)
    assert response.json()['records'][0]['shortname'] == new_user_data['shortname']


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_user_already_exist(client: AsyncClient):
    response = await client.get("/user/check-existing", params=new_user_data)
    assert_code_and_status_success(response)
    assert response.json()["attributes"]["unique"] is False

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_otp_request_login_success(client: AsyncClient):
    payload = {
        "email": new_user_data["email"]
    }

    response = await client.post("/user/otp-request-login", json=payload)
    assert_code_and_status_success(response)


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_otp_validation_success(client: AsyncClient):
    request_body = {
        "email": new_user_data["email"],
        "otp": "123456",  
    }

    response = await client.post("/user/login", json=request_body)
    assert_code_and_status_success(response)

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_otp_login_invalid_otp(client: AsyncClient):
    payload = {
        "email": new_user_data["email"],
        "otp": "000000"  
    }

    response = await client.post("/user/login", json=payload)
    json_response = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert json_response.get("status") == "failed"
    assert json_response.get("error", {}).get("type") == "auth"
    assert json_response.get("error", {}).get("code") == InternalErrorCode.INVALID_USERNAME_AND_PASS
    assert json_response.get("error", {}).get("message") == "Invalid username or password"


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_otp_both_email_and_msisdn_error(client: AsyncClient):
    payload = {
        "email": new_user_data["email"],
        "msisdn": new_user_data["msisdn"],
        "otp": "123456",
    }

    response = await client.post("/user/login", json=payload)
    json_response = response.json()
    
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert json_response["error"]["type"] == "general"
    assert json_response["error"]["code"] == 99
    assert "Too many input has been passed" in json_response["error"]["message"]

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_otp_unresolvable_identifier(client: AsyncClient):
    payload = {
        "email": "unknown_user@email.com",
        "otp": "123456",
    }

    response = await client.post("/user/login", json=payload)
    json_response = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert json_response["error"]["code"] == InternalErrorCode.INVALID_USERNAME_AND_PASS



@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_empty_otp_field(client: AsyncClient):
    payload = {
        "email": new_user_data["email"],
        "otp": ""  
    }

    response = await client.post("/user/login", json=payload)
    json_response = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert json_response["error"]["code"] == InternalErrorCode.INVALID_USERNAME_AND_PASS
    assert json_response["error"]["message"] == "Invalid username or password"


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_otp_but_missing_identifier(client: AsyncClient):
    response = await client.post("/user/login", json={"otp": "123456"})
    json_response = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert json_response["error"]["code"] == InternalErrorCode.INVALID_USERNAME_AND_PASS
    assert json_response["error"]["message"] == "Invalid username or password"


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_update_profile(client: AsyncClient) -> None:
    request_data = {
        "resource_type": ResourceType.user,
        "subpath": "users",
        "shortname": new_user_data["shortname"],
        "attributes": {"displayname": {"en": "New User"}},
    }

    assert_code_and_status_success(await client.post("/user/profile", json=request_data))


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_delete_new_user_profile(client: AsyncClient) -> None:
    response = await client.post("/user/delete", json={})
    assert_code_and_status_success(response)



@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_superman(client: AsyncClient):
    await set_superman_cookie(client)


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_get_superman_profile(client: AsyncClient) -> None:
    response = await client.get("/user/profile")
    assert_code_and_status_success(response)
    assert response.json()['records'][0]['shortname'] == superman['shortname']

