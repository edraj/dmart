import json
from pathlib import Path
from unittest.mock import patch, AsyncMock
import aiofiles
import pytest

from main import app
from models.core import User, Payload
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
from models.enums import QueryType, ResourceType, ContentType
from utils.internal_error_code import InternalErrorCode
from utils.jwt import sign_jwt
from utils.password_hashing import hash_password, verify_password
from utils.settings import settings
from utils import regex, db
from utils.custom_validations import validate_payload_with_schema
from httpx import AsyncClient


new_user_data = {
    "shortname": "tests_user_100100",
    "msisdn": "7777778220",
    "email": "test_user_100100@mymail.com",
}
new_user_data2 = {
    "shortname": "test_uuu_1002100",
    "msisdn": "77772117529",
    "email": "test_usesr___we@mymail.com",
}

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_update_profile_old_password_verification(client: AsyncClient) -> None:
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": "testuser",
        "attributes": {"password": "NewPassword123!", "old_password": "OldPassword123!"}
    }

    existing_user_data = {
        'shortname': 'testuser',
        'password': 'oldhashedpassword',
        'owner_shortname': 'owner'
    }

    with patch("utils.jwt.JWTBearer.__call__", return_value="testuser"), \
         patch("utils.db.load", return_value=User(**existing_user_data)), \
         patch("utils.password_hashing.verify_password", return_value=False):
        response = await client.post("/user/profile", json=request_data)

        # Assert response code and status failure
        assert response.status_code == 401
        assert response.json()['error']['message'] == "mismatch with the information provided"

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

# @pytest.mark.run(order=1)
# @pytest.mark.anyio
# async def test_create_user_with_payload_body(client: AsyncClient):
#     await set_superman_cookie(client)
#
#     request_body_valid_payload = {
#         "resource_type": "user",
#         "shortname": new_user_data2["shortname"],
#         "subpath": USERS_SUBPATH,
#         "attributes": {
#             "invitation": "valid_invitation_token",
#             "is_active": True,
#             "is_email_verified": True,
#             "is_msisdn_verified": True,
#             "password": "Test1234",
#             "email": new_user_data2["email"],
#             "msisdn": new_user_data2["msisdn"],
#             "roles": [],
#             "payload": {
#                 "content_type": "json",
#                 "schema_shortname": "api",
#                 "body": {
#                     "end_point": "",
#                     "verb": "post",
#                     "key1": "value1",
#                     "key2": "value2"
#                 }
#             }
#         },
#     }
#
#     response = await client.post("/user/create", json=request_body_valid_payload)
#     assert_code_and_status_success(response)
#
#     assert response.status_code == 200
#
#     separate_payload_data = {
#         "end_point": "",
#         "verb": "post",
#         "key1": "value1",
#         "key2": "value2"
#     }
#     await validate_payload_with_schema(
#         payload_data=separate_payload_data,
#         space_name=MANAGEMENT_SPACE,
#         schema_shortname="api"
#     )

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_none_shortname(client: AsyncClient):
    response = await client.post(
        "/user/login",
        json={
            "shortname": None,
            "email": "test_user_100100@mymail.com",
            "password": "Test1234",
        },
    )
    assert response.status_code == 401, f"Expected 401, got {response.status_code} with body {response.text}"

    response_json = response.json()
    assert response_json['error']['type'] == "auth"
    assert response_json['error']['code'] == 10
    assert response_json['error']['message'] == "Invalid username or password [1]"




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
@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_login_with_invalid_invitation(client: AsyncClient):
    fake_jwt = (
        "eyJhbGciOiJub25lIn0"  # Base64 of {"alg":"none"}
        ".eyJ1c2VyIjoiZG1hcnQiLCJleHAiOjEwMDAwfQ"  # Base64 of {"user":"dmart","exp":10000}
        ".c2lnbmF0dXJl"  # Base64 of "signature"
    )

    # await set_superman_cookie(client)

    # Using the hardcoded fake JWT
    payload = {
        "shortname": "dmart",
        "password": "Test1234",
        "invitation": fake_jwt,
    }

    response = await client.post("/user/login", json=payload)
    assert response.status_code == 401, f"Expected 401, got {response.status_code} with body {response.text}"

    response_json = response.json()
    assert response_json['error']['type'] == "jwtauth"
    assert response_json['error']['code'] == InternalErrorCode.INVALID_INVITATION
    assert response_json['error']['message'] == "Invalid invitation"


#TODO : Finsih the Whole Login Testing
@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_update_profile_displayname(client: AsyncClient) -> None:
    await set_superman_cookie(client)

    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": new_user_data["shortname"],
        "attributes": {"displayname": {"en": "New User"}},
    }

    # Make the authenticated request
    response = await client.post("/user/profile", json=request_data)
    assert response.status_code == 200

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_update_profile_invalid_password_format(client: AsyncClient) -> None:
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": "testuser",
        "attributes": {"password": "invalidpassword"}
    }

    with patch("utils.jwt.JWTBearer.__call__", return_value="testuser"):
        response = await client.post("/user/profile", json=request_data)

        assert response.status_code == 401
        assert response.json()['error']['message'] == "Invalid username or password"



@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_update_profile_confirmation_code(client: AsyncClient) -> None:
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": "testuser",
        "attributes": {"confirmation": "123456", "email": "new@example.com"}
    }

    existing_user_data = {
        'shortname': 'testuser',
        'email': 'old@example.com',
        'owner_shortname': 'owner'
    }

    with patch("utils.jwt.JWTBearer.__call__", return_value="testuser"), \
         patch("utils.db.load", return_value=User(**existing_user_data)), \
         patch("utils.redis_services.RedisServices.get_content_by_id", AsyncMock(return_value="wrongcode")):
        response = await client.post("/user/profile", json=request_data)

        assert response.status_code == 422
        assert response.json()['error']['message'] == "Invalid confirmation code [1]"

# @pytest.mark.run(order=1)
# @pytest.mark.anyio
# async def test_update_profile_payload(client: AsyncClient) -> None:
#     request_data = {
#         "resource_type": "user",
#         "subpath": "users",
#         "shortname": "testuser",
#         "attributes": {
#             "payload": {
#                 "content_type": ContentType.json,
#                 "body": {"key": "value"}
#             }
#         }
#     }
#
#     existing_user_data = {
#         'shortname': 'testuser',
#         'owner_shortname': 'owner',
#         'payload': Payload(
#             content_type=ContentType.json,
#             schema_shortname="user_profile",
#             body=""
#         )
#     }
#
#     with patch("utils.jwt.JWTBearer.__call__", return_value="testuser"), \
#          patch("utils.db.load", return_value=User(**existing_user_data)), \
#          patch("utils.db.save_payload_from_json", return_value=None), \
#          patch("utils.custom_validations.validate_payload_with_schema", return_value=None):
#         response = await client.post("/user/profile", json=request_data)
#
#         assert response.status_code == 200
#         assert response.json()['status'] == 'success'

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_update_profile_valid(client: AsyncClient) -> None:
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": "testuser",
        "attributes": {"displayname": {"en": "New User"}}
    }

    existing_user_data = {
        'shortname': 'testuser',
        'email': 'old@example.com',
        'displayname': {'en': 'Old User'},
        'msisdn': '1234567890',
        'type': 'web',
        'language': 'english',
        'is_email_verified': True,
        'is_msisdn_verified': True,
        'force_password_change': False,
        'roles': ['user'],
        'groups': ['group1'],
        'owner_shortname': 'owner',
        'password': 'hashedpassword',
        'payload': Payload(
            content_type=ContentType.json,
            schema_shortname="user_profile",
            body="{}",
        )
    }

    with patch("utils.jwt.JWTBearer.__call__", return_value=existing_user_data['shortname']), \
         patch("utils.db.load", return_value=User(**existing_user_data)), \
         patch("utils.access_control.AccessControl.get_user_permissions", AsyncMock(return_value=['read', 'write'])), \
         patch("utils.repository.get_entry_attachments", return_value={'user': ['avatar.png']}), \
         patch("utils.db.update", return_value=[]), \
         patch("utils.plugin_manager.plugin_manager.before_action", return_value=None), \
         patch("utils.plugin_manager.plugin_manager.after_action", return_value=None):

        response = await client.post("/user/profile", json=request_data)

        assert response.status_code == 200
        assert response.json()['status'] == 'success'

@pytest.mark.run(order=1)
@pytest.mark.anyio
async def test_get_profile_with_payload(client: AsyncClient) -> None:
    payload_content = {"key": "value"}
    payload_filename = "payload.json"

    user_data = {
        'shortname': 'testuser',
        'email': 'test@example.com',
        'displayname': {'en': 'Test User'},
        'msisdn': '1234567890',
        'type': 'web',
        'language': 'english',
        'is_email_verified': True,
        'is_msisdn_verified': True,
        'force_password_change': False,
        'roles': ['user'],
        'groups': ['group1'],
        'owner_shortname': 'owner',
        'payload': {
            'content_type': ContentType.json,
            'body': payload_filename
        }
    }

    payload_path = Path(settings.spaces_folder) / "management" / "users" / payload_filename
    payload_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(payload_path, 'w') as f:
        await f.write(json.dumps(payload_content))

    with patch("utils.jwt.JWTBearer.__call__", return_value=user_data['shortname']), \
         patch("utils.db.load", return_value=User(**user_data)), \
         patch("utils.access_control.AccessControl.get_user_permissions", AsyncMock(return_value=['read', 'write'])), \
         patch("utils.repository.get_entry_attachments", return_value={'user': ['avatar.png']}):

        response = await client.get("/user/profile")

        assert response.status_code == 200
        assert response.json()['status'] == 'success'
        response_data = response.json()
        assert response_data['records'][0]['shortname'] == user_data['shortname']
        assert response_data['records'][0]['attributes']['payload']['body'] == payload_content




