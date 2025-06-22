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
            "roles": ["manager","moderator","editor"],
            "email": "user1@example.com",
            "msisdn": "1123456789",
            "type": "bot",
            "payload": {

                "content_type": "json",
                "body": {
                    "is_subscribed": False,
                    "account_type": "business",
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
            "roles": ["member","subscriber","editor"],
            "email": "user2@example.com",
            "msisdn": "9876543210",
            "type": "mobile",
            "payload": {

                "content_type": "json",
                "body": {
                    "is_subscribed": True,
                    "account_type": "personal",
                    "allowed_categories": ["posts", "edits"]                          
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
async def test_basic_string_queries(client: AsyncClient) -> None:

    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@language:kurdish"
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
            "search": "-@language:arabic"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2
@pytest.mark.anyio
async def test_combined_string_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@language:kurdish|english"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 2



@pytest.mark.anyio
async def test_array_field_queries(client: AsyncClient) -> None:
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
    assert json_response["attributes"]["returned"] == 1

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
async def test_nested_payload_queries(client: AsyncClient) -> None:

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
            "search": "@payload.body.account_type:business"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1


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
async def test_combined_search_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@payload.body.account_type:business @payload.body.allowed_categories:analytics"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1


@pytest.mark.anyio
async def test_boolean_field_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/managed/query",
        json={
            "type": QueryType.search,
            "space_name": MANAGEMENT_SPACE,
            "subpath": USERS_SUBPATH,
            "search": "@is_active:false @roles:editor"
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
            "search": "@payload.body.is_subscribed:true @roles:editor"
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
            "search": "@payload.body.is_subscribed:true @roles:editor"
        }
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == 1
