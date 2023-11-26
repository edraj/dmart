import json
import pytest
from pytests.base_test import (
    assert_code_and_status_success,
    set_superman_cookie,
    client,
    MANAGEMENT_SPACE,
    USERS_SUBPATH,
)
from utils.settings import settings
from ldap3 import AUTO_BIND_NO_TLS, Server, Connection, ALL


set_superman_cookie()

with open("../backend/plugins/ldap_manager/config.json", "r") as plugin_conf:
    ldap_plugin_config = json.load(plugin_conf)

with open(
    f"{settings.spaces_folder}/{MANAGEMENT_SPACE}/.dm/meta.space.json", "r"
) as space_conf:
    management_space_config = json.load(space_conf)


ldap_active = True

if (
    ldap_plugin_config.get("is_active") is not True
    or "ldap_manager" not in management_space_config.get("active_plugins", [])
    or not settings.ldap_url
    or not settings.ldap_root_dn
    or not settings.ldap_admin_dn
    or not settings.ldap_pass
):
    ldap_active = False

ldap_conn : Connection | None = None

try:
    ldap_conn = Connection(
        Server("127.0.0.1", get_info=ALL),
        user=settings.ldap_admin_dn,
        password=settings.ldap_pass,
        auto_bind=AUTO_BIND_NO_TLS,
    )
except Exception:
    ldap_conn = None


@pytest.mark.run(order=4)
def test_ldap_user_created():
    if not ldap_active:
        return

    request_body = {
        "space_name": MANAGEMENT_SPACE,
        "request_type": "create",
        "records": [
            {
                "resource_type": "user",
                "shortname": "ldap_user_100100",
                "subpath": USERS_SUBPATH,
                "attributes": {
                    "is_active": True,
                    "password": "Test1234",
                    "email": "ldap_user_100100@ldap.com",
                    "msisdn": "7777123220",
                    "is_email_verified": True,
                    "is_msisdn_verified": True,
                },
            }
        ],
    }

    response = client.post("/managed/request", json=request_body)
    assert_code_and_status_success(response)

    ldap_entry = ldap_get_first_entry("ldap_user_100100")
    assert ldap_entry.get("dn") == f"cn=ldap_user_100100,{settings.ldap_root_dn}"


@pytest.mark.run(order=4)
def test_ldap_user_updated():
    if not ldap_active:
        return

    request_body = {
        "space_name": MANAGEMENT_SPACE,
        "request_type": "update",
        "records": [
            {
                "resource_type": "user",
                "shortname": "ldap_user_100100",
                "subpath": USERS_SUBPATH,
                "attributes": {
                    "displayname": {
                        "en": "En User",
                        "ar": "Ar User",
                        "kd": "Kd User",
                    }
                },
            }
        ],
    }

    response = client.post("/managed/request", json=request_body)
    assert_code_and_status_success(response)

    ldap_entry = ldap_get_first_entry("ldap_user_100100")
    assert (
        ldap_entry.get("attributes", {}).get("givenName", [])[0]
        == "en='En User' ar='Ar User' kd='Kd User'"
    )


@pytest.mark.run(order=4)
def test_ldap_user_deleted():
    if not ldap_active:
        return

    request_body = {
        "space_name": MANAGEMENT_SPACE,
        "request_type": "delete",
        "records": [
            {
                "resource_type": "user",
                "shortname": "ldap_user_100100",
                "subpath": USERS_SUBPATH,
                "attributes": {},
            }
        ],
    }

    response = client.post("/managed/request", json=request_body)
    assert_code_and_status_success(response)

    ldap_entry = ldap_get_first_entry("ldap_user_100100")
    assert ldap_entry.get("dn") == ""


def ldap_get_first_entry(shortname: str) -> dict:
    if not ldap_conn:
        return {"dn": "", "attributes": {}}

    ldap_conn.search(
        search_base=f"cn={shortname},{settings.ldap_root_dn}",
        search_filter="(objectclass=dmartUser)",
        attributes=["cn", "gn"],
    )

    if ldap_conn.response: 
        for entry in ldap_conn.response:
            if isinstance(entry, dict):
                return entry

    return {"dn": "", "attributes": {}}
