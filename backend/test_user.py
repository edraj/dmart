import os
import shutil

import redis
from fastapi.testclient import TestClient
from fastapi import status
from test_utils import assert_code_and_status_success, check_not_found

from main import app
from utils.settings import settings


client = TestClient(app)

DEMO_SPACE: str = "demo"
MANAGEMENT_SPACE: str = f"{settings.management_space}"
USERS_SUBPATH: str = "users"

INVITATION = "ABCxyz"
SHORTNAME = "alibaba"
DISPLAYNAME = {"en": "Ali Baba"}
EMAIL = "ali@baba.com"
PASSWORD = "Password1234"
INVITATION = "ABCxyz"

dirpath = f"{settings.spaces_folder}/{MANAGEMENT_SPACE}/{USERS_SUBPATH}/.dm/{SHORTNAME}"
filepath = f"{dirpath}/meta.user.json"

def test_create():
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
    data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": SHORTNAME,
        "attributes": {
            "displayname": DISPLAYNAME,
            "email": EMAIL,
            "password": PASSWORD,
            "invitation": "hello",
        },
    }
    assert_code_and_status_success(client.post(endpoint, json=data, headers=headers))

    response = client.post(endpoint, json={**data, "attributes": {}}, headers=headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = client.post(
        endpoint,
        json={
            **data,
            "attributes": {
                "displayname": DISPLAYNAME,
                "email": EMAIL,
                "password": PASSWORD,
            },
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = client.post(
        endpoint,
        json={
            **data,
            "attributes": {
                "displayname": DISPLAYNAME,
                "email": EMAIL,
                "invitation": "hello",
            },
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_login():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/login"
    request_data = {"shortname": SHORTNAME, "password": PASSWORD}

    check_not_found(
        client.post(
            endpoint, json={**request_data, "shortname": "shortname"}, headers=headers
        )
    )

    response = client.post(
        endpoint, json={**request_data, "password": "IncorrectPassword1234"}, headers=headers
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json().get("status") == "failed"
    assert response.json().get("error").get("type") == "auth"

    response = client.post(endpoint, json=request_data, headers=headers)
    assert_code_and_status_success(response)
    client.cookies.set("auth_token", response.cookies["auth_token"])


def test_update():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/profile"
    request_data = {
        "resource_type": "user",
        "subpath": "users",
        "shortname": SHORTNAME,
        "attributes": {
            "displayname": {"en": "New display name"},
            "email": "new@email.com",
            "password": "Password12345",
        },
    }
    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )


def test_logout():
    headers = {"Content-Type": "application/json"}
    endpoint = "/user/logout"
    request_data = {"shortname": SHORTNAME, "password": PASSWORD}

    assert_code_and_status_success(
        client.post(endpoint, json=request_data, headers=headers)
    )
