"""Extended tests for models/core.py, models/api.py validators, and utils/ticket_sys_utils.py pure functions."""

import pytest
from pydantic import ValidationError

from models.api import Query, RedisAggregate, RedisReducer
from models.core import (
    Content,
    Notification,
    Payload,
    Record,
    User,
    deep_update,
)
from models.enums import (
    ContentType,
    NotificationType,
    QueryType,
    ResourceType,
)
from utils.ticket_sys_utils import check_open_state, post_transite, transite

# ==================== deep_update ====================


def test_deep_update_non_dict_overwrite():
    result = deep_update({"a": {"b": 1}}, {"a": "replaced"})
    assert result["a"] == "replaced"


def test_deep_update_merge():
    result = deep_update({"a": {"b": 1, "c": 2}}, {"a": {"b": 10}})
    assert result == {"a": {"b": 10, "c": 2}}


def test_deep_update_add_key():
    result = deep_update({"a": 1}, {"b": 2})
    assert result == {"a": 1, "b": 2}


# ==================== Payload ====================


def test_payload_checksum_none_body():
    p = Payload(content_type=ContentType.json, body=None)
    # Force checksum calculation for None body
    p._calculate_checksum()
    assert p.checksum is not None


def test_payload_checksum_str_body():
    p = Payload(content_type=ContentType.json, body="somefile.json")
    p._calculate_checksum()
    assert p.checksum is not None


def test_payload_checksum_dict_body():
    p = Payload(content_type=ContentType.json, body={"key": "value"})
    assert p.checksum is not None  # auto-calculated in __init__


def test_payload_update_none_body():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    result = p.update({"body": None})
    assert result is None


def test_payload_update_no_old_body():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    result = p.update({"body": {"b": 2}})
    assert result == {"b": 2}
    assert p.body == {"b": 2}


def test_payload_update_replace():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    result = p.update({"body": {"b": 2}}, old_body={"a": 1}, replace=True)
    assert result == {"b": 2}


def test_payload_update_merge_with_old_body():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    result = p.update({"body": {"b": 2}}, old_body={"a": 1, "c": 3})
    assert result is not None
    assert result["a"] == 1
    assert result["b"] == 2
    assert result["c"] == 3


def test_payload_update_non_dict_body():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    result = p.update({"body": "file.json"})
    assert result is None
    assert p.body == "file.json"


def test_payload_update_with_schema():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    result = p.update({"body": {"b": 2}, "schema_shortname": "my_schema"})
    assert p.schema_shortname == "my_schema"


def test_payload_update_content_type():
    p = Payload(content_type=ContentType.json, body={"a": 1})
    p.update({"body": {"b": 2}, "content_type": "text"})
    assert p.content_type == ContentType.text


# ==================== Record ====================


def test_record_to_dict():
    r = Record(resource_type=ResourceType.content, shortname="test", subpath="/data", attributes={"key": "val"})
    d = r.to_dict()
    assert isinstance(d, dict)
    assert d["shortname"] == "test"
    assert "uuid" not in d  # excluded because None


def test_record_equality():
    r1 = Record(resource_type=ResourceType.content, shortname="test", subpath="/data", attributes={})
    r2 = Record(resource_type=ResourceType.content, shortname="test", subpath="/data", attributes={"extra": True})
    assert r1 == r2  # equality based on shortname + subpath


def test_record_inequality():
    r1 = Record(resource_type=ResourceType.content, shortname="test1", subpath="/data", attributes={})
    r2 = Record(resource_type=ResourceType.content, shortname="test2", subpath="/data", attributes={})
    assert r1 != r2


# ==================== Meta.update_from_record ====================


def test_meta_update_from_record_password_hashing():
    user = User(shortname="testuser", owner_shortname="admin", password="oldpass")
    record = Record(
        resource_type=ResourceType.user,
        shortname="testuser",
        subpath="/users",
        attributes={"password": "newpass"},
    )
    user.update_from_record(record)
    assert user.password != "newpass"  # should be hashed
    assert user.password is not None


def test_meta_update_from_record_creates_payload():
    content = Content(shortname="test", owner_shortname="admin")
    assert content.payload is None
    record = Record(
        resource_type=ResourceType.content,
        shortname="test",
        subpath="/data",
        attributes={
            "payload": {"content_type": "json", "body": {"x": 1}},
        },
    )
    content.update_from_record(record)
    assert content.payload is not None


def test_meta_update_from_record_updates_payload():
    content = Content(
        shortname="test",
        owner_shortname="admin",
        payload=Payload(content_type=ContentType.json, body={"a": 1}),
    )
    record = Record(
        resource_type=ResourceType.content,
        shortname="test",
        subpath="/data",
        attributes={"payload": {"body": {"b": 2}}},
    )
    result = content.update_from_record(record, old_body={"a": 1})
    assert result is not None
    assert result["a"] == 1
    assert result["b"] == 2


# ==================== Meta.to_record ====================


def test_meta_to_record_shortname_mismatch():
    content = Content(shortname="abc", owner_shortname="admin")
    with pytest.raises(Exception, match="shortname in meta"):
        content.to_record("/data", "wrong_name")


def test_meta_to_record_success():
    content = Content(shortname="test", owner_shortname="admin", is_active=True)
    record = content.to_record("/data", "test")
    assert record.shortname == "test"
    assert record.subpath == "data"  # Record strips leading/trailing slashes
    assert record.attributes["is_active"] is True


# ==================== Notification.from_request ====================


@pytest.mark.anyio
async def test_notification_from_request_admin():
    req = {
        "payload": {"schema_shortname": "admin_notification_request", "body": {"priority": "high"}},
        "displayname": {"en": "Test"},
        "description": {"en": "Desc"},
        "owner_shortname": "admin",
    }
    notif = await Notification.from_request(req)
    assert notif.type == NotificationType.admin
    assert notif.is_read is False
    assert notif.entry is None


@pytest.mark.anyio
async def test_notification_from_request_system():
    req = {
        "payload": {"schema_shortname": "system_notification_request", "body": {"priority": "low"}},
        "displayname": {"en": "Sys"},
        "description": {"en": "Desc"},
        "owner_shortname": "system",
    }
    notif = await Notification.from_request(req)
    assert notif.type == NotificationType.system


@pytest.mark.anyio
async def test_notification_from_request_with_entry():
    req = {
        "payload": {"schema_shortname": "admin_notification_request", "body": {"priority": "medium"}},
        "displayname": {"en": "Test"},
        "description": {"en": "Desc"},
        "owner_shortname": "admin",
    }
    entry = {
        "space_name": "data",
        "resource_type": "content",
        "payload": {"schema_shortname": "ticket"},
        "subpath": "/tickets",
        "shortname": "t1",
    }
    notif = await Notification.from_request(req, entry)
    assert notif.entry is not None
    assert notif.entry.space_name == "data"


@pytest.mark.anyio
async def test_notification_from_request_unknown_schema():
    req = {
        "payload": {"schema_shortname": "unknown_schema", "body": {"priority": "high"}},
        "displayname": {"en": "Test"},
        "description": {"en": "Desc"},
        "owner_shortname": "admin",
    }
    notif = await Notification.from_request(req)
    assert notif.type == NotificationType.admin  # falls through to default


# ==================== api.py validators (error branches) ====================


def test_reducer_name_invalid_chars():
    with pytest.raises(ValidationError, match="reducer_name"):
        RedisReducer(reducer_name="DROP TABLE; --")


def test_reducer_alias_invalid_chars():
    with pytest.raises(ValidationError, match="alias"):
        RedisReducer(reducer_name="SUM", alias="bad; chars")


def test_aggregate_group_by_invalid():
    with pytest.raises(ValidationError, match="group_by"):
        RedisAggregate(group_by=["valid", "bad; field"])


def test_query_sort_by_invalid():
    with pytest.raises(ValidationError, match="sort_by"):
        Query(type=QueryType.search, space_name="test", subpath="/", sort_by="field; DROP TABLE")


def test_query_jq_filter_dangerous():
    with pytest.raises(ValidationError, match="jq_filter"):
        Query(type=QueryType.search, space_name="test", subpath="/", jq_filter=".data | env")


def test_query_filter_shortnames_invalid():
    with pytest.raises(ValidationError, match="filter_shortnames"):
        Query(type=QueryType.search, space_name="test", subpath="/", filter_shortnames=["valid", "bad name!@#"])


# ==================== ticket_sys_utils pure functions ====================

STATES = [
    {
        "state": "open",
        "next": [
            {"action": "approve", "state": "approved", "roles": ["admin", "manager"]},
            {"action": "reject", "state": "rejected", "roles": ["admin"]},
        ],
    },
    {
        "state": "approved",
        "resolutions": ["fixed", "wontfix"],
    },
    {
        "state": "closed_with_dict_resolutions",
        "resolutions": [{"key": "resolved"}, {"key": "duplicate"}],
    },
    {
        "state": "empty_resolutions",
        "resolutions": [],
    },
]


def test_transite_success():
    result = transite(STATES, "open", "approve", ["admin"])
    assert result["status"] is True
    assert result["message"] == "approved"


def test_transite_no_role():
    result = transite(STATES, "open", "approve", ["viewer"])
    assert result["status"] is False
    assert "permission" in result["message"]


def test_transite_invalid_action():
    result = transite(STATES, "open", "nonexistent", ["admin"])
    assert result["status"] is False
    assert "can't progress" in result["message"].lower()


def test_transite_invalid_state():
    result = transite(STATES, "unknown", "approve", ["admin"])
    assert result["status"] is False


def test_post_transite_valid_string():
    result = post_transite(STATES, "approved", "fixed")
    assert result["status"] is True
    assert result["message"] == "fixed"


def test_post_transite_invalid_resolution():
    result = post_transite(STATES, "approved", "nonexistent")
    assert result["status"] is False
    assert "not acceptable" in result["message"]


def test_post_transite_dict_resolutions():
    result = post_transite(STATES, "closed_with_dict_resolutions", "resolved")
    assert result["status"] is True


def test_post_transite_empty_resolutions():
    result = post_transite(STATES, "empty_resolutions", "anything")
    assert result["status"] is False
    assert "does not have any resolutions" in result["message"]


def test_post_transite_state_not_found():
    result = post_transite(STATES, "nonexistent", "fixed")
    assert result["status"] is False
    assert "Cannot fetch" in result["message"]


def test_check_open_state_open():
    assert check_open_state(STATES, "open") is True


def test_check_open_state_closed():
    assert check_open_state(STATES, "approved") is False


def test_check_open_state_unknown():
    assert check_open_state(STATES, "nonexistent") is True
