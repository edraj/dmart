import pytest
from datetime import datetime, timedelta
from models.enums import QueryType, ResourceType, RequestType
from httpx import AsyncClient
from pytests.base_test import (
    USERS_SUBPATH,
    MANAGEMENT_SPACE,
    assert_code_and_status_success,
)

TEST_DATA = [
    {
        "shortname": "user1",
        "attributes": {
            "tags": ["test_user"],
            "is_active": False,
            "language": "kurdish",
            "roles": ["manager", "moderator"],
            "email": "user1@example.com",
            "msisdn": "1123456789",
            "type": "bot",
            "payload": {
                "content_type": "json",
                "body": {
                    "is_subscribed": False,
                    "account_type": "business",
                    "user_gender": "male",
                    "account_number": 100,
                    "rating": "5",
                    "allowed_categories": ["analytics", "reviews"]
                }
            }
        }
    },
    {
        "shortname": "user2",
        "attributes": {
            "tags": ["test_user"],
            "is_active": False,
            "language": "english",
            "roles": ["manager"],
            "email": "user2@example.com",
            "msisdn": "9876543210",
            "type": "mobile",
            "payload": {
                "content_type": "json",
                "body": {
                    "is_subscribed": True,
                    "account_type": "personal",
                    "user_gender": "female",
                    "account_number": 200,
                    "rating": "4",
                    "allowed_categories": ["posts", "edits"],
                    "x":{"y": {"z":5}}
                }
            }
        }
    }
]


@pytest.fixture(autouse=True)
async def setup_teardown(client: AsyncClient):
    for data in TEST_DATA:
        response = await client.post(
            "/managed/request",
            json={
                "space_name": MANAGEMENT_SPACE,
                "request_type": RequestType.create,
                "records": [{
                    "resource_type": ResourceType.user,
                    "subpath": USERS_SUBPATH,
                    "shortname": data["shortname"],
                    "attributes": data["attributes"]
                }]
            }
        )
        assert_code_and_status_success(response)

    yield

    for data in TEST_DATA:
        await client.post(
            "/managed/request",
            json={
                "space_name": MANAGEMENT_SPACE,
                "request_type": RequestType.delete,
                "records": [{
                    "attributes": {},
                    "resource_type": ResourceType.user,
                    "subpath": USERS_SUBPATH,
                    "shortname": data["shortname"]
                }]
            }
        )


@pytest.mark.anyio
async def test_string_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@language:ku"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@msisdn:1123456789"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@email:user1@example.com"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@language:ar"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@is_active:False @roles:moderator"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@is_active:True -@roles:world"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@language:en @msisdn:9876543210"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@roles:super_admin -@language:ar"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@language:ku|en"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@language:ar|fr"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2


@pytest.mark.anyio
async def test_array_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@roles:manager"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@roles:manager"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 3

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@roles:manager|moderator"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@roles:super_admin|world"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2


@pytest.mark.anyio
async def test_array_payload_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.allowed_categories:posts"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.allowed_categories:posts"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.allowed_categories:posts @payload.body.allowed_categories:edits"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.allowed_categories:posts -@payload.body.allowed_categories:edits"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.allowed_categories:posts|reviews"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.allowed_categories:posts|reviews"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 0


@pytest.mark.anyio
async def test_string_payload_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.account_type:business"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.account_type:business"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.account_type:personal @payload.body.user_gender:female"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.account_type:business -@payload.body.user_gender:male"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.account_type:business|personal"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.account_type:business|personal"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 0

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.account_number:100"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.account_number:100"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.rating:5"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.rating:5"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.rating:5|4"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.rating:5|4"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 0


@pytest.mark.anyio
async def test_date_field_queries(client: AsyncClient) -> None:
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": f"@created_at:{formatted_time}"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 0

    start_date = (current_time - timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (current_time + timedelta(days=1)).strftime("%Y-%m-%d")
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": f"@created_at:[{start_date},{end_date}]"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2


@pytest.mark.anyio
async def test_boolean_field_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@is_active:false @roles:manager"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@is_active:false @roles:manager"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 0

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.is_subscribed:false"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "-@payload.body.is_subscribed:true"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1


@pytest.mark.anyio
async def test_nested_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.x.y.z:5"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1
