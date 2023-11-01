import pathmagic
import json
from fastapi.testclient import TestClient
from main import app
from utils.redis_services import RedisServices
from utils.plugin_manager import plugin_manager
from utils.settings import settings
from fastapi import status
from models.api import Query
from models.enums import QueryType

client = TestClient(app, headers={"Content-Type": "application/json"})


superman = {}
alibaba = {}

file = open("../backend/login_creds.sh", "r")
for line in file.readlines():
    if line.strip().startswith("export SUPERMAN"):
        superman = json.loads(str(line.strip().split("'")[1]))
    if line.strip().startswith("export ALIBABA"):
        alibaba = json.loads(str(line.strip().split("'")[1]))


MANAGEMENT_SPACE: str = f"{settings.management_space}"
USERS_SUBPATH: str = "users"
RedisServices.is_pytest = True
plugin_manager.is_pytest = True


def set_superman_cookie():
    response = client.post(
        "/user/login",
        json={"shortname": superman["shortname"], "password": superman["password"]},
    )
    print(
        f"\n\n\n\n ===>> SUPER MAN USER LOGGED IN <====== {response.json() = } \n\n\n"
    )
    client.cookies.set("auth_token", response.cookies["auth_token"])


def set_alibaba_cookie():
    response = client.post(
        "/user/login",
        json={"shortname": superman["shortname"], "password": superman["password"]},
    )
    client.cookies.set("auth_token", response.cookies["auth_token"])


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
    assert json_response["status"] == "success"


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
