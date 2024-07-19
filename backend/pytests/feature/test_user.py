import http

import pytest
from httpx import AsyncClient

from api.user.models.requests import UserLoginRequest
from models import api
from pytests.base_test import (
    assert_code_and_status_success,
    assert_resource_created,
    set_superman_cookie,
    MANAGEMENT_SPACE,
    USERS_SUBPATH,
    superman
)
from fastapi import status
from models.api import Query
from models.enums import QueryType, ResourceType
from utils.settings import settings
from utils import regex

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
async def test_create_user(client: AsyncClient):
    request_body = {
        "resource_type": "user",
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            "invitation": "",
            "is_active": True,
            "is_email_verified": True,
            "is_msisdn_verified": True,
            "password": "Test1234",
            "email": new_user_data["email"],
            "msisdn": new_user_data["msisdn"],
            "roles": [],
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
async def test_update_profile(client: AsyncClient) -> None:
    request_data = {
        "resource_type": "user",
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


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_create_user_registration_disabled(client: AsyncClient):
    # Save the original value of settings.is_registrable
    original_is_registrable = settings.is_registrable
    settings.is_registrable = False

    request_body = {
        "resource_type": "user",
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            "invitation": "",
            "is_active": True,
            "is_email_verified": True,
            "is_msisdn_verified": True,
            "password": "Test1234",
            "email": new_user_data["email"],
            "msisdn": new_user_data["msisdn"],
            "roles": [],
        },
    }

    response = await client.post("/user/create", json=request_body)

    # Revert settings.is_registrable to its original value
    settings.is_registrable = original_is_registrable

    # Assert response status and content
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "status": "failed",
        "error": {
            "type": "create",
            "code": 50,
            "message": "Register API is disabled",
            "info": None
        },
        "records": None,
        "attributes": None
    }


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_create_user_missing_invitation(client: AsyncClient):
    settings.is_registrable = True

    request_body = {
        "resource_type": "user",
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            # "invitation": "",  # This is intentionally omitted to trigger the exception
            "is_active": True,
            "is_email_verified": True,
            "is_msisdn_verified": True,
            "password": "Test1234",
            "email": new_user_data["email"],
            "msisdn": new_user_data["msisdn"],
            "roles": [],
        },
    }

    response = await client.post("/user/create", json=request_body)

    # Assert response status and content
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "status": "failed",
        "error": {
            "type": "create",
            "code": 50,
            "message": "bad or missing invitation token",
            "info": None
        },
        "records": None,
        "attributes": None
    }


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_create_user_passwd_attribute(client: AsyncClient):
    settings.is_registrable = True

    request_body = {
        "resource_type": "user",
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            "invitation": "",
            "is_active": True,
            "is_email_verified": True,
            "is_msisdn_verified": True,
            # "password": "Test1234", # commented to thow the exception
            "email": new_user_data["email"],
            "msisdn": new_user_data["msisdn"],
            "roles": [],
        },
    }

    response = await client.post("/user/create", json=request_body)

    # Assert response status and content
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "status": "failed",
        "error": {
            "type": "create",
            "code": 50,
            "message": "empty password",
            "info": None
        },
        "records": None,
        "attributes": None
    }


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_create_user_passwd_attribute(client: AsyncClient):
    settings.is_registrable = True

    request_body = {
        "resource_type": "user",
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            "invitation": "",
            "is_active": True,
            "is_email_verified": True,
            "is_msisdn_verified": True,
            # "password": "Test1234", # commented to thow the exception
            "email": new_user_data["email"],
            "msisdn": new_user_data["msisdn"],
            "roles": [],
        },
    }

    response = await client.post("/user/create", json=request_body)

    # Assert response status and content
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "status": "failed",
        "error": {
            "type": "create",
            "code": 50,
            "message": "empty password",
            "info": None
        },
        "records": None,
        "attributes": None
    }


@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_create_user_invalid_password(client: AsyncClient):
    # Set an invalid regex pattern to ensure the password validation fails
    regex.PASSWORD = "321321321321321"

    request_body = {
        "resource_type": "user",
        "shortname": new_user_data["shortname"],
        "subpath": USERS_SUBPATH,
        "attributes": {
            "invitation": "",
            "is_active": True,
            "is_email_verified": True,
            "is_msisdn_verified": True,
            "password": "Test1234",  # Provide a password to test the regex validation
            "email": new_user_data["email"],
            "msisdn": new_user_data["msisdn"],
            "roles": [],
        },
    }

    response = await client.post("/user/create", json=request_body)

    # Assert response status and content
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "status": "failed",
        "error": {
            "type": "jwtauth",
            "code": 14,
            "message": "password dose not match required rules",
            "info": None
        },
        "records": None,
        "attributes": None
    }


# TODO : This Test Case is Created To cover the attribute and body Case in Create user APi
# @pytest.mark.run(order=1)
# @pytest.mark.anyio
# async def test_create_user_with_payload(client: AsyncClient):
#     # Define the request body with the example payload structure
#     await set_superman_cookie(client)
#     request_body = {
#         "space_name": "applications",
#         "request_type": "create",
#         "records": [
#             {
#                 "resource_type": "content",
#                 "shortname": "test178002121002",
#                 "subpath": "api/user",
#                 "attributes": {
#                     "is_active": True,
#                     "relationships": [],
#                     "payload": {
#                         "content_type": "json",
#                         "schema_shortname": None,
#                         "body": {
#                             "content_type": "json",
#                             "schema_shortname": "api",
#                             "body": {
#                                 "email": "myname@gmail.com",
#                                 "first_name": "John",
#                                 "language": "en",
#                                 "last_name": "Doo",
#                                 "mobile": "7999311703"
#                             }
#                         }
#                     }
#                 }
#             }
#         ]
#     }
#
#     # Make a POST request to the endpoint
#     response = await client.post("http://localhost:8282/managed/request", json=request_body)
#
#     # Print the response for debugging
#     print(response.json())
#
#     # Assert response status and content
#     assert response.status_code == 200
#     assert response.json()["status"] == "success"


# @pytest.mark.run(order=1)
# @pytest.mark.anyio
# async def test_login_with_invalid_invitation(client: AsyncClient):
#     await set_superman_cookie(client)
#
#     response = await client.post(
#         "/user/login",
#         json={
#             "shortname": "dmart",  # Ensure this is a valid value
#             "email": None,
#             "msisdn": None,
#             "password": "Test1234",
#             "invitation": "invalid-token",  # Ensure this is an invalid token
#             "firebase_token": None
#         },
#     )
#
#     # Assert the response status and error message
#     assert response.status_code == 401
#     response_json = response.json()
#     assert response_json['error']['type'] == "jwtauth"
#     assert response_json['error']['code'] == InternalErrorCode.INVALID_INVITATION
#     assert response_json['error']['message'] == "Invalid invitation"
