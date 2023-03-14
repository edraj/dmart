import json
import shutil
from fastapi.testclient import TestClient
from fastapi import status
from models.enums import ResourceType
from test_utils import check_repeated_shortname, assert_code_and_status_success, check_not_found
from utils.settings import settings
import os
from models.api import Query, QueryType

from pytest_mock import mocker
from main import app

client = TestClient(app)


creds_file = open("login_creds.sh", "r")
Lines = creds_file.readlines()
superman={}
alibaba={}
for line in Lines:
    if line.strip().startswith("export SUPERMAN"):
        data = line.strip().split('\'')[1]
        superman = json.loads(str(data))
    if line.strip().startswith("export ALIBABA"):
        data = line.strip().split('\'')[1]
        alibaba = json.loads(str(data))


DEMO_SPACE: str = f"test"
DEFAULT_BRANCH: str = settings.default_branch
USERS_SUBPATH: str = "users"

user_shortname: str = superman["shortname"]
password: str = superman["password"]

subpath: str = "content"
text_entry_shortname: str = "text_stuff"
json_entry_shortname: str = "json_stuff"
attachment_shortname: str = "my_comment"


schema_record_path = f"../sample/test/createschema.json"
schema_shortname = "test_schema"
schema_payload_path = f"../sample/test/schema.json"

content_record_path = f"../sample/test/createcontent.json"
content_shortname = "buyer_123"
content_payload_path = f"../sample/test//data.json"
attachment_record_path = f"../sample/test/createmedia.json"
attachment_payload_path = f"../sample/test/logo.jpeg"

content_media_record_path = f"../sample/test/createmedia_entry.json"
content_media_payload_path = f"../sample/test/logo.jpeg"

resources_schema_shortname = "test_schema"
resources_csv_path = f"../sample/test/resources.csv"
csv_num_of_records = 11
num_of_created_entries = 0

dirpath = f"{settings.spaces_folder}/{DEMO_SPACE}/{subpath}"
if os.path.exists(dirpath):
    shutil.rmtree(dirpath)


def test_login():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/login"
    request_data = {"shortname": user_shortname, "password": password}

    response = client.post(endpoint, json=request_data, headers=headers)
    assert_code_and_status_success(response)

    client.cookies.set("auth_token", response.cookies.get("auth_token"))
    check_not_found(
        client.post(
            endpoint, json={**request_data, "shortname": "shortname"}, headers=headers
        )
    )

    # response = client.post(
    #     endpoint, json={**request_data, "password": "WRONG_PASS"}, headers=headers
    # )

    # assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # assert response.json().get("status") == "failed"
    # assert response.json().get("error").get("type") == "auth"


def test_get_profile():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/profile"
    response = client.get(endpoint, headers=headers)
    assert_code_and_status_success(response)


def test_create_folder_resource():
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "create",
        "records": [
            {
                "resource_type": "folder",
                "subpath": "/",
                "shortname": subpath,
                "attributes": {},
            }
        ],
    }

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )

    assert_resource_created(
        query=Query(
            type=QueryType.subpath,
            space_name=DEMO_SPACE,
            subpath="/",
            filter_shortnames=[subpath],
            filter_types=[ResourceType.folder],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=subpath,
        res_subpath="/",
        res_attributes={},
    )

    check_repeated_shortname(
        client.post(
            endpoint,
            json=request_data,
            headers=headers,
        )
    )


def test_create_text_content_resource(mocker):
    global num_of_created_entries
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    attributes = {"payload": {"content_type": "text", "body": "this is a text content"}}
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "create",
        "records": [
            {
                "resource_type": "content",
                "subpath": subpath,
                "shortname": text_entry_shortname,
                "attributes": attributes,
            }
        ],
    }

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )

    assert_resource_created(
        query=Query(
            type=QueryType.subpath,
            space_name=DEMO_SPACE,
            subpath=subpath,
            filter_shortnames=[text_entry_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=text_entry_shortname,
        res_subpath=subpath,
        res_attributes=attributes,
    )

    check_repeated_shortname(
        client.post(endpoint, json=request_data, headers=headers)
    )
    num_of_created_entries += 1

    response = client.post(
        endpoint, json={**request_data, "space_name": "space_name"}, headers=headers
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = client.post(
        endpoint, json={**request_data, "records": []}, headers=headers
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # mocker.patch("utils.access_control.access_control.check_access", return_value=None)
    # response = client.post(endpoint, json=request_data, headers=headers)
    # assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # response = client.post(
    #     endpoint, json={**request_data, "request_type": "update"}, headers=headers
    # )
    # assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # response = client.post(
    #     endpoint, json={**request_data, "request_type": "delete"}, headers=headers
    # )
    # assert response.status_code == status.HTTP_401_UNAUTHORIZED
    #! TODO
    # response = client.post(
    #     endpoint, json={**request_data, "request_type": "move"}, headers=headers
    # )
    # print(response.json())
    # assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_upload_schema_resource():
    upload_resource_with_payload(
        DEMO_SPACE, schema_record_path, schema_payload_path, "application/json"
    )


def test_create_json_content_resource():
    global num_of_created_entries
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    attributes = {
        "payload": {
            "content_type": "json",
            "schema_shortname": resources_schema_shortname,
            "body": {"price": 25.99, "name": "Buyer"},
        }
    }
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "create",
        "records": [
            {
                "resource_type": "content",
                "subpath": subpath,
                "shortname": json_entry_shortname,
                "attributes": attributes,
            }
        ],
    }

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )

    assert_resource_created(
        query=Query(
            type=QueryType.subpath,
            space_name=DEMO_SPACE,
            subpath=subpath,
            filter_shortnames=[json_entry_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=json_entry_shortname,
        res_subpath=subpath,
        res_attributes=attributes,
    )

    check_repeated_shortname(
        client.post(
            endpoint,
            json=request_data,
            headers=headers,
        )
    )
    num_of_created_entries += 1


def test_update_json_content_resource():
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    attributes = {
        "payload": {
            "content_type": "json",
            "schema_shortname": resources_schema_shortname,
            "body": {"price": 25000.99, "name": "Buyer UPDATEDDDD"},
        }
    }
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "update",
        "records": [
            {
                "resource_type": "content",
                "subpath": subpath,
                "shortname": json_entry_shortname,
                "attributes": attributes,
            }
        ],
    }

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )

    assert_resource_created(
        query=Query(
            type=QueryType.subpath,
            space_name=DEMO_SPACE,
            subpath=subpath,
            filter_shortnames=[json_entry_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=json_entry_shortname,
        res_subpath=subpath,
        res_attributes=attributes,
    )



def test_create_comment_attachment():
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "create",
        "records": [
            {
                "resource_type": "comment",
                "subpath": f"{subpath}/{json_entry_shortname}",
                "shortname": attachment_shortname,
                "attributes": {"body": "A very speed car"},
            }
        ],
    }

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )

    assert_resource_created(
        query=Query(
            type=QueryType.subpath,
            space_name=DEMO_SPACE,
            subpath=subpath,
            filter_shortnames=[json_entry_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=json_entry_shortname,
        res_subpath=subpath,
        res_attachments={"comment": 1},
    )

    check_repeated_shortname(
        client.post(
            endpoint,
            json=request_data,
            headers=headers,
        )
    )


def test_entry(mocker):
    # /entry/{resource_type}/{space_name}/{subpath:path}/{shortname}
    endpoint = f"managed/entry/content/{DEMO_SPACE}/{subpath}/{json_entry_shortname}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK
    endpoint = f"public/entry/content/{DEMO_SPACE}/{subpath}/{json_entry_shortname}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    endpoint = f"managed/entry/content/{DEMO_SPACE}/{subpath}/json_entry_shortname"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    endpoint = f"public/entry/content/{DEMO_SPACE}/{subpath}/json_entry_shortname"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    mocker.patch("utils.access_control.access_control.check_access", return_value=None)
    endpoint = f"managed/entry/content/{DEMO_SPACE}/{subpath}/{json_entry_shortname}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    mocker.patch("utils.db.load", return_value=None)
    endpoint = f"managed/entry/content/{DEMO_SPACE}/{subpath}/{json_entry_shortname}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    endpoint = f"public/entry/content/{DEMO_SPACE}/{subpath}/{json_entry_shortname}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_reload_redis(mocker):
    endpoint = "managed/reload-redis-data?for_space=test"
    response = client.post(endpoint)
    assert response.status_code == status.HTTP_200_OK

    # mocker.patch("utils.access_control.access_control.check_access", return_value=None)
    # response = client.get(endpoint)
    # assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_reload_security_data(mocker):
    endpoint = "managed/reload-security-data"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK


def test_upload_json_content_resource():
    global num_of_created_entries
    upload_resource_with_payload(
        DEMO_SPACE, content_record_path, content_payload_path, "application/json"
    )
    num_of_created_entries += 1


def test_upload_resource_with_payload_attached_to_entry():
    upload_resource_with_payload(
        DEMO_SPACE, attachment_record_path, attachment_payload_path, "image/jpeg", True
    )

    assert_resource_created(
        query=Query(
            type=QueryType.subpath,
            space_name=DEMO_SPACE,
            subpath=subpath,
            filter_shortnames=[content_shortname],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=content_shortname,
        res_subpath=subpath,
    )


def test_upload_media_content_resource():
    global num_of_created_entries
    upload_resource_with_payload(
        DEMO_SPACE, content_media_record_path, content_media_payload_path, "image/jpeg"
    )
    num_of_created_entries += 1


def test_retrieve_attachment(mocker):
    with open(attachment_record_path, "rb") as request_file:
        request_file_data = json.load(request_file)

        subpath = request_file_data["subpath"]
        file_name = (
            request_file_data["shortname"]
            + "."
            + attachment_payload_path.split(".")[-1]
        )

    # Retrieve from MANAGED API
    endpoint = f"managed/payload/media/{DEMO_SPACE}/{subpath}/{file_name}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK
    # Retrieve from PUBLIC API
    endpoint = f"public/payload/media/{DEMO_SPACE}/{subpath}/{file_name}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK

    endpoint = f"managed/payload/media/{DEMO_SPACE}/{subpath}/qsdqsd.gif"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    endpoint = f"managed/payload/media/{DEMO_SPACE}/{subpath}/qsdqsd.gif"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    mocker.patch("utils.db.load", return_value=MetaObj())
    endpoint = f"public/payload/media/{DEMO_SPACE}/{subpath}/{file_name}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    endpoint = f"managed/payload/media/{DEMO_SPACE}/{subpath}/{file_name}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_upload_resource_from_csv():
    global num_of_created_entries
    endpoint = f"managed/resources_from_csv/content/{DEMO_SPACE}/{subpath}/{resources_schema_shortname}"
    with open(resources_csv_path, "rb") as csv_file:
        assert_code_and_status_success(
            client.post(endpoint, files=[("resources_file", ("data.csv", csv_file))])
        )
    num_of_created_entries += csv_num_of_records


def test_query_subpath():
    global csv_num_of_records
    limit = 200
    filter_types = ["content"]
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/query"
    request_data = {
        "type": "subpath",
        "space_name": DEMO_SPACE,
        "subpath": subpath,
        "filter_types": filter_types,
        "filter_shortnames": [],
        "limit": limit,
        "offset": 0,
    }

    response = client.post(endpoint, json=request_data, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == num_of_created_entries

    endpoint = "/public/query"
    response = client.post(endpoint, json=request_data, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    endpoint = f"/public/query/spaces/{DEMO_SPACE}/{subpath}"
    response = client.get(endpoint)

    assert response.status_code == status.HTTP_200_OK


def test_delete_all():
    # DELETE CONTENT RESOURCE
    response = delete_resource(
        resource="content", del_subpath=subpath, del_shortname=json_entry_shortname
    )
    assert_code_and_status_success(response=response)

    # DELETE FOLDER RESOURCE
    response = delete_resource(
        resource="folder", del_subpath="/", del_shortname=subpath
    )
    assert_code_and_status_success(response=response)

    # DELETE SCHEMA RESOURCE
    response = delete_resource(
        resource="schema", del_subpath="schema", del_shortname=schema_shortname
    )
    assert_code_and_status_success(response=response)

    path = settings.spaces_folder / DEMO_SPACE / subpath
    if path.is_dir():
        shutil.rmtree(path)

    path = settings.spaces_folder / DEMO_SPACE / ".dm/events.jsonl"
    if path.is_file():
        os.remove(path)


def test_health():
    endpoint = f"/managed/health/{DEMO_SPACE}"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK

    endpoint = f"/managed/health/DEMO_SPACE"
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def delete_resource(resource: str, del_subpath: str, del_shortname: str):
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "delete",
        "records": [
            {
                "resource_type": resource,
                "subpath": del_subpath,
                "shortname": del_shortname,
                "attributes": {},
            }
        ],
    }

    return client.post(endpoint, json=request_data, headers=headers)


def upload_resource_with_payload(
    space_name,
    record_path: str,
    payload_path: str,
    payload_type,
    attachment=False,
    is_fail=False,
):
    endpoint = "managed/resource_with_payload"
    with open(record_path, "rb") as request_file:
        media_file = open(payload_path, "rb")

        # BufferedReader
        request_file_data = json.load(request_file)
        payload_subpath = request_file_data["subpath"]
        payload_shortname = request_file_data["shortname"]

        request_file.seek(0)
        data = [
            ("request_record", ("record.json", request_file, "application/json")),
            (
                "payload_file",
                (media_file.name.split("/")[-1], media_file, payload_type),
            ),
        ]
        if is_fail:
            response = client.post(
                endpoint, data={"space_name": space_name}, files=data
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
        else:
            assert_code_and_status_success(
                client.post(endpoint, data={"space_name": space_name}, files=data)
            )

    media_file.close()

    if not attachment:
        assert_resource_created(
            query=Query(
                type=QueryType.subpath,
                space_name=space_name,
                subpath=payload_subpath,
                filter_shortnames=[payload_shortname],
                retrieve_json_payload=True,
                limit=1,
            ),
            res_shortname=payload_shortname,
            res_subpath=payload_subpath,
            res_attachments={"media": 1},
        )


def upload_resource_with_payload_wrong_space(
    record_path: str, payload_path: str, payload_type, attachment=False
):
    endpoint = "managed/resource_with_payload"
    with open(record_path, "rb") as request_file:
        media_file = open(payload_path, "rb")

        # BufferedReader
        request_file_data = json.load(request_file)
        payload_subpath = request_file_data["subpath"]
        payload_shortname = request_file_data["shortname"]

        request_file.seek(0)
        data = [
            ("request_record", ("record.json", request_file, "application/json")),
            (
                "payload_file",
                (media_file.name.split("/")[-1], media_file, payload_type),
            ),
        ]

        assert_code_and_status_success(
            client.post(endpoint, data={"space_name": "DEMO_SPACE"}, files=data)
        )

    media_file.close()

    if not attachment:
        assert_resource_created(
            query=Query(
                type=QueryType.subpath,
                space_name=DEMO_SPACE,
                subpath=payload_subpath,
                filter_shortnames=[payload_shortname],
                retrieve_json_payload=True,
                limit=1,
            ),
            res_shortname=payload_shortname,
            res_subpath=payload_subpath,
            res_attachments={"media": 1},
        )


def assert_resource_created(
    query: Query,
    res_shortname: str,
    res_subpath: str,
    res_attributes: dict | None = None,
    res_attachments: dict[str, int] | None = None,
):
    response = client.post(
        "/managed/query",
        json=json.loads(query.json(exclude_none=True)),
        headers={"Content-Type": "application/json"},
    )
    assert_code_and_status_success(response)
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["attributes"]["returned"] == query.limit
    assert json_response["records"][0]["shortname"] == res_shortname
    assert json_response["records"][0]["subpath"] in [res_subpath, f"/{res_subpath}"]
    if res_attributes:
        if "is_active" not in res_attributes:
            res_attributes["is_active"] = False
        if "tags" not in res_attributes:
            res_attributes["tags"] = []
        res_attributes["owner_shortname"] = "dmart"

        json_response["records"][0]["attributes"].pop("created_at", None)
        json_response["records"][0]["attributes"].pop("updated_at", None)
        assert json_response["records"][0]["attributes"]["payload"]["body"] == res_attributes["payload"]["body"]

    # Assert correct attachments number for each attachment type returned
    if res_attachments:
        for attachment_key, attachments in json_response["records"][0][
            "attachments"
        ].items():
            if attachment_key in res_attachments:
                assert len(attachments) == res_attachments[attachment_key]


class MetaObj(object):
    payload = None
