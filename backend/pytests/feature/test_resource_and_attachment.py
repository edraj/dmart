import pytest
from httpx import AsyncClient
from pytests.base_test import (
    assert_bad_request,
    assert_code_and_status_success,
    assert_resource_created,
    assert_resource_deleted,
    check_repeated_shortname,
    delete_resource,
    delete_space,
    init_test_db,
    set_superman_cookie,
    DEMO_SPACE,
    DEMO_SUBPATH,
    upload_resource_with_payload,
    retrieve_content_folder,
)
from fastapi import status
from models.api import Query
from models.enums import QueryType, ResourceType, ContentType, RequestType
from utils.settings import settings




@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_retrieve_content_folder(client: AsyncClient):
    await init_test_db(client)
    await set_superman_cookie(client)
    await retrieve_content_folder(client)


schema_record_path = "pytests/data/record_of_schema.json"
schema_shortname = "test_schema"
schema_payload_path = "pytests/data/payload_of_schema.json"

text_entry_shortname: str = "text_stuff"
json_entry_shortname: str = "json_stuff"
json_entry_uuid: str = ""

content_record_path = "pytests/data/record_of_content.json"
content_shortname = "buyer_123"
content_payload_path = "pytests/data/payload_of_content.json"

media_record_path = "pytests/data/record_of_media.json"
media_shortname = "logo.jpeg"
media_payload_path = "pytests/data/logo.jpeg"

resources_csv_path = "pytests/data/resources.csv"


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_create_text_content_resource(client: AsyncClient):
    attributes = {"payload": {"content_type": ContentType.text, "body": "this is a text content"}}
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": RequestType.create,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": DEMO_SUBPATH,
                "shortname": text_entry_shortname,
                "attributes": attributes,
            }
        ],
    }

    assert_code_and_status_success(await client.post("/managed/request", json=request_data))

    await assert_resource_created(
        client,
        query=Query(
            type=QueryType.search,
            space_name=DEMO_SPACE,
            subpath=DEMO_SUBPATH,
            filter_shortnames=[text_entry_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=text_entry_shortname,
        res_subpath=DEMO_SUBPATH,
        res_attributes=attributes,
    )

    check_repeated_shortname(await client.post("/managed/request", json=request_data))


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_upload_schema_resource(client: AsyncClient) -> None:
    await upload_resource_with_payload(
        client,
        DEMO_SPACE, schema_record_path, schema_payload_path, "application/json"
    )


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_create_json_content_resource(client: AsyncClient) -> None:
    global json_entry_uuid
    endpoint = "/managed/request"
    attributes = {
        "slug": f"{json_entry_shortname}_slug",
        "payload": {
            "content_type": ContentType.json,
            "schema_shortname": schema_shortname,
            "body": {"price": 25.99, "name": "Buyer"},
        },
    }
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": RequestType.create,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": DEMO_SUBPATH,
                "shortname": json_entry_shortname,
                "attributes": attributes,
            }
        ],
    }

    response = await client.post(endpoint, json=request_data)
    assert_code_and_status_success(response)

    await assert_resource_created(
        client,
        query=Query(
            type=QueryType.search,
            space_name=DEMO_SPACE,
            subpath=DEMO_SUBPATH,
            filter_shortnames=[json_entry_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=json_entry_shortname,
        res_subpath=DEMO_SUBPATH,
        res_attributes=attributes,
    )

    json_entry_uuid = response.json()["records"][0]["uuid"]

    check_repeated_shortname(
        await client.post(
            endpoint,
            json=request_data,
        )
    )


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_create_invalid_json_resource(client: AsyncClient):
    global json_entry_uuid
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": RequestType.create,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": DEMO_SUBPATH,
                "shortname": "auto",
                "attributes": {
                    "payload": {
                        "content_type": ContentType.json,
                        "schema_shortname": schema_shortname,
                        "body": {"price": "25.99", "name": "Buyer"},
                    }
                },
            }
        ],
    }

    assert_bad_request(await client.post("/managed/request", json=request_data))


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_update_json_content_resource(client: AsyncClient) -> None:
    endpoint = "/managed/request"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": RequestType.update,
        "records": [
            {
                "resource_type": ResourceType.content,
                "subpath": DEMO_SUBPATH,
                "shortname": json_entry_shortname,
                "attributes": {
                    "payload": {
                        "content_type": ContentType.json,
                        "schema_shortname": schema_shortname,
                        "body": {"price": 25000.99, "name": "Buyer UPDATEDDDD"},
                    },
                },
            }
        ],
    }

    assert_code_and_status_success(await client.post(endpoint, json=request_data))


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_create_comment_attachment(client: AsyncClient) -> None:
    endpoint = "/managed/request"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": RequestType.create,
        "records": [
            {
                "resource_type": ResourceType.comment,
                "subpath": f"{DEMO_SUBPATH}/{json_entry_shortname}",
                "shortname": "my_comment",
                "attributes": {"body": "A very speed car", "state": "on_road"},
            }
        ],
    }

    assert_code_and_status_success(await client.post(endpoint, json=request_data))

    await assert_resource_created(
        client,
        query=Query(
            type=QueryType.search,
            space_name=DEMO_SPACE,
            subpath=DEMO_SUBPATH,
            filter_shortnames=[json_entry_shortname],
            retrieve_json_payload=True,
            retrieve_attachments=True,
            limit=1,
        ),
        res_shortname=json_entry_shortname,
        res_subpath=DEMO_SUBPATH,
        res_attachments={"comment": 1},
    )

    check_repeated_shortname(await client.post(endpoint, json=request_data))


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_get_entry_from_managed(client: AsyncClient):
    response = await client.get(
        f"managed/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/{json_entry_shortname}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["uuid"] == json_entry_uuid


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_get_entry_by_uuid(client: AsyncClient):
    response = await client.get(f"managed/byuuid/{json_entry_uuid.split('-')[0]}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["uuid"] == json_entry_uuid


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_get_entry_by_slug(client: AsyncClient):
    response = await client.get(f"managed/byslug/{json_entry_shortname}_slug")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["uuid"] == json_entry_uuid


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_get_not_found_entry(client: AsyncClient):
    response = await client.get(
        f"managed/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/json_entry_shortname"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_get_unauthorized_resource_from_managed_api(client, mocker):
    mocker.patch("utils.access_control.access_control.check_access", return_value=None)
    response = await client.get(
        f"managed/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/{json_entry_shortname}"
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_get_unauthorized_entry_from_public_api(client: AsyncClient):
    response = await client.get(
        f"public/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/{json_entry_shortname}"
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_upload_json_content_resource(client: AsyncClient) -> None:
    await upload_resource_with_payload(
        client,
        DEMO_SPACE, content_record_path, content_payload_path, "application/json"
    )


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_upload_image_attachment(client: AsyncClient) -> None:
    await upload_resource_with_payload(
        client,
        DEMO_SPACE, media_record_path, media_payload_path, "image/jpeg", True
    )


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_retrieve_attachment(client: AsyncClient):
    # Retrieve from MANAGED API
    endpoint = f"managed/payload/media/{DEMO_SPACE}/{DEMO_SUBPATH}/{content_shortname}/{media_shortname}"
    response = await client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK

    # Retrieve from PUBLIC API
    endpoint = f"public/payload/media/{DEMO_SPACE}/{DEMO_SUBPATH}/{content_shortname}/{media_shortname}"
    response = await client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.run(order=2)
@pytest.mark.anyio
async def test_upload_resource_from_csv(client: AsyncClient) -> None:
    with open(resources_csv_path, "rb") as csv_file:
        no_of_rows = len(csv_file.readlines()) - 1

        csv_file.seek(0)

        response = await client.post(
            f"managed/resources_from_csv/content/{DEMO_SPACE}/{DEMO_SUBPATH}/{schema_shortname}",
            files=[("resources_file", ("data.csv", csv_file))],
        )
        assert_code_and_status_success(response)

        assert response.json()["attributes"]["success_count"] == no_of_rows


@pytest.mark.run("last")
@pytest.mark.anyio
async def test_delete_attachment(client: AsyncClient):
    await delete_resource(
        client,
        ResourceType.media,
        f"{DEMO_SUBPATH}/{content_shortname}",
        media_shortname.split(".")[0],
    )

    response = await client.get(f"managed/payload/media/{DEMO_SPACE}/{DEMO_SUBPATH}/{content_shortname}/{media_shortname}")
    assert (response.status_code == status.HTTP_404_NOT_FOUND)


@pytest.mark.anyio
async def test_delete_content(client: AsyncClient):
    await delete_resource(client, ResourceType.content, DEMO_SUBPATH, content_shortname)

    await assert_resource_deleted(client, DEMO_SPACE, DEMO_SUBPATH, content_shortname)

    response = await client.get(f"managed/entry/content/{DEMO_SPACE}/{DEMO_SUBPATH}/{content_shortname}")

    assert (response.status_code == status.HTTP_404_NOT_FOUND)


@pytest.mark.run("last")
@pytest.mark.anyio
async def test_delete_folder(client: AsyncClient):
    await delete_resource(client, ResourceType.folder, "/", DEMO_SUBPATH)

    await assert_resource_deleted(client, DEMO_SPACE, settings.root_subpath_mw, DEMO_SUBPATH)

    response = await client.get(f"managed/entry/folder/{DEMO_SPACE}/{settings.root_subpath_mw}/{DEMO_SUBPATH}")
    assert (response.status_code == status.HTTP_404_NOT_FOUND
    )


@pytest.mark.run("last")
@pytest.mark.anyio
async def test_delete_space(client: AsyncClient):
    await delete_space(client)


@pytest.mark.run("last")
@pytest.mark.anyio
async def test_logout(client: AsyncClient):
    response = await client.post("/user/logout", json={})
    assert_code_and_status_success(response)
