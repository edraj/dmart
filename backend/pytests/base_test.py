import json
from fastapi.testclient import TestClient
from main import app
from utils.redis_services import RedisServices
from utils.plugin_manager import plugin_manager
from utils.settings import settings
from fastapi import status
from models.api import Query
from models.enums import QueryType, ResourceType

client = TestClient(app)


superman = {}
alibaba = {}

file = open("./login_creds.sh", "r")
for line in file.readlines():
    if line.strip().startswith("export SUPERMAN"):
        superman = json.loads(str(line.strip().split("'")[1]))
    if line.strip().startswith("export ALIBABA"):
        alibaba = json.loads(str(line.strip().split("'")[1]))

MANAGEMENT_SPACE: str = f"{settings.management_space}"
USERS_SUBPATH: str = "users"
DEMO_SPACE: str = "test"
DEMO_SUBPATH: str = "content"
DEFAULT_BRANCH: str = settings.default_branch
RedisServices.is_pytest = True
plugin_manager.is_pytest = True


def set_superman_cookie():
    response = client.post(
        "/user/login",
        json={"shortname": superman["shortname"], "password": superman["password"]},
    )
    print(f"\n {response.json() = } \n")
    assert response.status_code == status.HTTP_200_OK
    client.cookies.set("auth_token", response.cookies["auth_token"])


def set_alibaba_cookie():
    response = client.post(
        "/user/login",
        json={"shortname": superman["shortname"], "password": superman["password"]},
    )
    print(f"\n {response.json() = } \n")
    assert response.status_code == status.HTTP_200_OK
    client.cookies.set("auth_token", response.cookies["auth_token"])


def init_test_db() -> None:
    # Create the space
    client.post(
        "managed/space",
        json={
            "space_name": DEMO_SPACE,
            "request_type": "create",
            "records": [
                {
                    "resource_type": "space",
                    "subpath": "/",
                    "shortname": DEMO_SPACE,
                    "attributes": {},
                }
            ],
        },
    )

    # Create the folder
    client.post(
        "/managed/request",
        json={
            "space_name": DEMO_SPACE,
            "request_type": "create",
            "records": [
                {
                    "resource_type": "folder",
                    "subpath": "/",
                    "shortname": DEMO_SUBPATH,
                    "attributes": {},
                }
            ],
        },
    )


def delete_space() -> None:
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/space"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "delete",
        "records": [
            {
                "resource_type": "space",
                "subpath": "/",
                "shortname": DEMO_SPACE,
                "attributes": {},
            }
        ],
    }

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )
    check_not_found(
        client.get(f"/managed/entry/space/{DEMO_SPACE}/__root__/{DEMO_SPACE}")
    )


def check_repeated_shortname(response):
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "failed" == response.json().get("status")
    assert "request" == response.json().get("error", {}).get("type")


def check_not_found(response):
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "failed" == response.json().get("status")
    assert "db" == response.json().get("error").get("type")


def check_unauthorized(response):
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "failed" == response.json().get("status")
    assert "auth" == response.json().get("error", {}).get("type")


def assert_code_and_status_success(response):
    if response.status_code != status.HTTP_200_OK:
        print(
            "\n\n\n\n\n========================= ERROR RESPONSE: =========================n:",
            response.json(),
            "\n\n\n\n\n",
        )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response.get("status") == "success"
    

def assert_bad_request(response):
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["status"] == "failed"


def assert_resource_created(
    query: Query,
    res_shortname: str,
    res_subpath: str,
    res_attributes: dict | None = None,
    res_attachments: dict[str, int] | None = None,
):
    if not query.search:
        query.search = ""
    response = client.post(
        "/managed/query",
        json=query.model_dump(exclude_none=True),
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
        assert (
            json_response["records"][0]["attributes"]["payload"]["body"]
            == res_attributes["payload"]["body"]
        )

    # Assert correct attachments number for each attachment type returned
    if res_attachments:
        for attachment_key, attachments in json_response["records"][0][
            "attachments"
        ].items():
            if attachment_key in res_attachments:
                assert len(attachments) == res_attachments[attachment_key]


def assert_resource_deleted(space: str, subpath: str, shortname: str):
    query = Query(
        type=QueryType.search,
        space_name=space,
        subpath=subpath,
        search="",
        filter_shortnames=[shortname],
        retrieve_json_payload=True,
        limit=1,
    )
    response = client.post("/managed/query", json=query.model_dump(exclude_none=True))
    assert_code_and_status_success(response)
    assert response.json()["status"] == "success"
    assert response.json()["attributes"]["returned"] == 0


def upload_resource_with_payload(
    space_name,
    record_path: str,
    payload_path: str,
    payload_type,
    attachment=False,
    is_fail=False,
):
    with open(record_path, "rb") as request_file, open(
        payload_path, "rb"
    ) as media_file:
        files = {
            "request_record": ("record.json", request_file, "application/json"),
            "payload_file": (media_file.name.split("/")[-1], media_file, payload_type),
        }
        response = client.post(
            "managed/resource_with_payload",
            headers={},
            data={"space_name": space_name},
            files=files,
        )

    if is_fail:
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    else:
        assert_code_and_status_success(response)

    if attachment:
        with open(record_path, 'r') as record_file:
            record_data = json.loads(record_file.read())
            subpath_parts = record_data["subpath"].split('/')
            attach_parent_subpath, attach_parent_shortname = "/".join(subpath_parts[:-1]), subpath_parts[-1]
        assert_resource_created(
            query=Query(
                type=QueryType.search,
                space_name=space_name,
                subpath=attach_parent_subpath,
                filter_shortnames=[attach_parent_shortname],
                retrieve_json_payload=True,
                retrieve_attachments=True,
                limit=1,
            ),
            res_shortname=attach_parent_shortname,
            res_subpath=attach_parent_subpath,
            res_attachments={"media": 1},
        )


def delete_resource(resource_type: str, del_subpath: str, del_shortname: str):
    headers = {"Content-Type": "application/json"}
    endpoint = "/managed/request"
    request_data = {
        "space_name": DEMO_SPACE,
        "request_type": "delete",
        "records": [
            {
                "resource_type": resource_type,
                "subpath": del_subpath,
                "shortname": del_shortname,
                "attributes": {},
            }
        ],
    }

    response = client.post(endpoint, json=request_data, headers=headers)
    assert_code_and_status_success(response)


def retrieve_content_folder():
    assert client.get(
        f"managed/entry/folder/{DEMO_SPACE}/{settings.root_subpath_mw}/{DEMO_SUBPATH}"
    ).status_code == status.HTTP_200_OK
     
    assert_resource_created(
        query=Query(
            type=QueryType.search,
            space_name=DEMO_SPACE,
            subpath="/",
            filter_shortnames=[DEMO_SUBPATH],
            filter_types=[ResourceType.folder],
            retrieve_json_payload=True,
            limit=1,
        ),
        res_shortname=DEMO_SUBPATH,
        res_subpath="/",
        res_attributes={},
    )
