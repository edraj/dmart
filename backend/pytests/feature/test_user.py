import pytest
from httpx import AsyncClient
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
        "resource_type": ResourceType.user,
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
