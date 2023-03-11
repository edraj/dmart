import os
import shutil

import redis
from fastapi.testclient import TestClient
from fastapi import status

from test_utils import assert_code_and_status_success, check_not_found
# import test_managed as managed
from utils.settings import settings

from main import app

client = TestClient(app)

MANAGEMENT_SPACE: str = f"{settings.management_space}"
USERS_SUBPATH: str = "users"

shortname: str = "alibaba"
displayname: dict = {"en": "Ali Baba"}
email: str = "ali_neww@baba.com"
password: str = "OneTwoThree123"
invitation: str = "A1B2C3"
token: str = ""
subpath = "nicepost"

dirpath = f"{settings.spaces_folder}/{MANAGEMENT_SPACE}/{USERS_SUBPATH}/.dm/{shortname}"
filepath = f"{dirpath}/meta.user.json"

# TODO: remove test case dependencies from one another
def test_card():
    response = client.get("/")
    assert response.status_code == 200

def test_create_user():
    # TODO: remove dependencies of other tests to user registration test

    # TODO: create test_setup and test teardown
    # redis_client = redis.Redis(
    #     host=settings.redis_host,
    #     port=settings.redis_port, 
    #     password=settings.redis_password,
    # )
    # redis_client.delete("management:master:meta:users/alibaba")

    if os.path.exists(filepath):
        os.remove(filepath)

    if os.path.exists(dirpath):
        shutil.rmtree(dirpath)

    headers = {"Content-Type": "application/json"}
    endpoint = "/user/create"
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": shortname,
        "attributes": {
            "displayname": displayname,
            "email": email,
            "password": password,
            "invitation": invitation,
        },
    }
    response = client.post(endpoint, json=request_data, headers=headers)
    assert_code_and_status_success(response)


def test_login():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/login"
    request_data = {"shortname": shortname, "password": password}

    check_not_found(
        client.post(
            endpoint, json={**request_data, "shortname": "shortname"}, headers=headers
        )
    )

    response = client.post(
        endpoint, json={**request_data, "password": "IncorrectPasswordabc"}, headers=headers
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json().get("status") == "failed"
    assert response.json().get("error").get("type") == "auth"

    response = client.post(endpoint, json=request_data, headers=headers)
    assert_code_and_status_success(response)
    client.cookies.set("auth_token", response.cookies["auth_token"])


def test_get_profile():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/profile"
    response = client.get(endpoint, headers=headers)
    assert_code_and_status_success(response)


def test_update_profile():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/profile"
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": shortname,
        "attributes": {
            "displayname": displayname,
            "email": email,
        },
    }

    response = client.post(endpoint, json=request_data, headers=headers)
    assert_code_and_status_success(response)


def test_delete_user():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/delete"
    assert_code_and_status_success( client.post(endpoint, json={}, headers=headers) )


if __name__ == "__main__":
    test_create_user()
    test_login()
    test_get_profile()
    test_update_profile()
    # managed.test_create_content_resource()
    # managed.test_create_comment_resource()
    # managed.test_create_folder_resource()
    # # managed.test_upload_attachment_with_payload()
    # managed.test_query_subpath()
    # managed.test_delete_all()
