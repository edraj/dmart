"""Combined tests for various utility modules — covers uncovered branches and pure functions.

Targets: utils/jwt.py, utils/generate_email.py, utils/social_sso.py, utils/notification.py,
         utils/plugin_manager.py, main.py (mask_sensitive_data, set_middleware_response_headers),
         data_adapters/helpers.py
"""

import asyncio
from time import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest

import models.api as api
from data_adapters.helpers import get_nested_value, trans_magic_words
from main import mask_sensitive_data, set_middleware_response_headers
from models.core import ActionType, Event, EventFilter, PluginWrapper
from models.enums import EventListenTime, PluginType, ResourceType
from utils.generate_email import generate_email_from_template, generate_subject
from utils.jwt import decode_jwt, generate_jwt
from utils.notification import NotificationManager
from utils.plugin_manager import PluginManager
from utils.settings import settings


# ==================== data_adapters/helpers.py ====================


def test_get_nested_value_simple():
    assert get_nested_value({"a": 1}, "a") == 1


def test_get_nested_value_deep():
    assert get_nested_value({"a": {"b": {"c": 42}}}, "a.b.c") == 42


def test_get_nested_value_missing_key():
    assert get_nested_value({"a": {"b": 1}}, "a.x") is None


def test_get_nested_value_non_dict():
    assert get_nested_value({"a": 1}, "a.b") is None


def test_get_nested_value_empty():
    assert get_nested_value({}, "a") is None


def test_trans_magic_words_empty_result():
    old_mw = settings.current_user_mw
    result = trans_magic_words(old_mw, old_mw)
    # After replacing current_user_mw with itself, and removing double slashes
    assert isinstance(result, str)
    settings.current_user_mw = old_mw


def test_trans_magic_words_trailing_slash():
    result = trans_magic_words("/users/test/", "test")
    assert not result.endswith("/") or result == "/"


def test_trans_magic_words_with_owner():
    old_owner_mw = settings.current_user_owner_mw
    subpath = f"/data/{old_owner_mw}/items"
    result = trans_magic_words(subpath, "user1", "owner1")
    assert "owner1" in result
    assert old_owner_mw not in result


# ==================== utils/jwt.py ====================


def test_decode_jwt_invalid_token():
    with pytest.raises(api.Exception) as exc_info:
        decode_jwt("garbage.token.here")
    assert exc_info.value.status_code == 401
    assert "Invalid Token [1]" in exc_info.value.error.message


def test_decode_jwt_missing_data():
    token = pyjwt.encode({"expires": time() + 3600}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(api.Exception) as exc_info:
        decode_jwt(token)
    assert "Invalid Token [2]" in exc_info.value.error.message


def test_decode_jwt_expired():
    token = pyjwt.encode(
        {"data": {"shortname": "user"}, "expires": time() - 100},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(api.Exception) as exc_info:
        decode_jwt(token)
    assert "Expired Token" in exc_info.value.error.message


def test_decode_jwt_no_shortname():
    token = pyjwt.encode(
        {"data": {"other": "field"}, "expires": time() + 3600},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(api.Exception) as exc_info:
        decode_jwt(token)
    assert "Invalid Token [3]" in exc_info.value.error.message


def test_decode_jwt_valid():
    token = generate_jwt({"shortname": "testuser", "type": "web"})
    result = decode_jwt(token)
    assert result["shortname"] == "testuser"


def test_generate_jwt_roundtrip():
    data = {"shortname": "admin", "type": "bot"}
    token = generate_jwt(data, expires=3600)
    decoded = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert decoded["data"]["shortname"] == "admin"
    assert decoded["expires"] > time()


# ==================== utils/generate_email.py ====================


def test_generate_subject_activation():
    assert generate_subject("activation") == "Welcome to our Platform!"


def test_generate_subject_reminder():
    assert generate_subject("reminder") == "[Reminder] Activate Your Account"


def test_generate_subject_unknown():
    assert generate_subject("nonexistent") == ""


def test_generate_email_activation():
    result = generate_email_from_template(
        "activation",
        {
            "name": "Alice",
            "msisdn": "1234567890",
            "shortname": "alice",
            "link": "http://example.com",
        },
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_email_reminder():
    result = generate_email_from_template(
        "reminder",
        {
            "name": "Bob",
            "link": "http://example.com/activate",
        },
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_email_unknown():
    result = generate_email_from_template("nonexistent", {})
    assert result == ""


# ==================== utils/social_sso.py ====================


def test_get_facebook_sso():
    from utils.social_sso import get_facebook_sso

    sso = get_facebook_sso()
    assert sso is not None


def test_get_google_sso():
    from utils.social_sso import get_google_sso

    sso = get_google_sso()
    assert sso is not None


def test_apple_response_convertor():
    from utils.social_sso import apple_response_convertor

    response = {
        "sub": "user123",
        "email": "test@example.com",
        "fullName": "John Doe",
        "picture": "http://example.com/pic.jpg",
    }
    openid = apple_response_convertor(response)
    assert openid.id == "user123"
    assert openid.email == "test@example.com"
    assert openid.first_name == "John"
    assert openid.last_name == "Doe"
    assert openid.provider == "apple"


def test_get_apple_sso():
    from utils.social_sso import get_apple_sso

    sso = get_apple_sso()
    assert sso is not None


# ==================== main.py: mask_sensitive_data ====================


def test_mask_sensitive_data_dict():
    data: dict = {"username": "admin", "password": "secret123", "token": "abc"}
    result: dict = mask_sensitive_data(data)
    assert result["username"] == "admin"
    assert result["password"] == "******"
    assert result["token"] == "******"


def test_mask_sensitive_data_nested():
    data: dict = {"user": {"access_token": "xyz", "name": "Bob"}}
    result: dict = mask_sensitive_data(data)
    inner: dict = result["user"]
    assert inner["access_token"] == "******"
    assert inner["name"] == "Bob"


def test_mask_sensitive_data_list():
    data = [{"password": "secret"}, {"name": "Alice"}]
    result = mask_sensitive_data(data)
    assert isinstance(result, list)
    assert result[0]["password"] == "******"  # type: ignore[index]
    assert result[1]["name"] == "Alice"  # type: ignore[index]


def test_mask_sensitive_data_large_list():
    data = list(range(25))
    result = mask_sensitive_data(data)
    assert result == data  # returned as-is for lists > 20


def test_mask_sensitive_data_string_with_auth():
    result = mask_sensitive_data("cookie=auth_token=abc123")
    assert result == "******"


def test_mask_sensitive_data_depth_limit():
    # Nest beyond depth 4
    data: dict = {"a": {"b": {"c": {"d": {"e": {"password": "secret"}}}}}}
    masked = mask_sensitive_data(data)
    # At depth 5, recursion stops so "password" stays unmasked
    assert isinstance(masked, dict)
    deep = masked["a"]["b"]["c"]["d"]["e"]  # type: ignore[index]
    assert deep["password"] == "secret"  # type: ignore[index]


def test_mask_sensitive_data_primitives():
    assert mask_sensitive_data(42) == 42
    assert mask_sensitive_data(None) is None


# ==================== main.py: set_middleware_response_headers ====================


def test_set_middleware_response_headers_allowed_origin():
    old_origins = settings.allowed_cors_origins
    settings.allowed_cors_origins = ["http://localhost:3000"]  # type: ignore[assignment]

    mock_request = MagicMock()
    mock_request.headers.get.return_value = "http://localhost:3000"
    mock_request.url.path = "/api/test"
    mock_response = MagicMock()
    mock_response.headers = {}

    set_middleware_response_headers(mock_request, mock_response)
    assert mock_response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert mock_response.headers["Access-Control-Allow-Credentials"] == "true"

    settings.allowed_cors_origins = old_origins


def test_set_middleware_response_headers_static_cache():
    mock_request = MagicMock()
    mock_request.headers.get.return_value = ""
    mock_request.url.path = "/static/app.js"
    mock_response = MagicMock()
    mock_response.headers = {}

    set_middleware_response_headers(mock_request, mock_response)
    assert "public" in mock_response.headers["Cache-Control"]


# ==================== utils/notification.py ====================


@pytest.mark.anyio
async def test_notification_manager_send_unknown_platform():
    mgr = NotificationManager.__new__(NotificationManager)
    mgr.notifiers = {}
    result = await mgr.send("unknown_platform", MagicMock())
    assert result is False


@pytest.mark.anyio
async def test_notification_manager_send_success():
    mock_notifier = AsyncMock()
    mock_notifier.send = AsyncMock(return_value=True)
    mgr = NotificationManager.__new__(NotificationManager)
    mgr.notifiers = {"email": mock_notifier}
    result = await mgr.send("email", MagicMock())
    assert result is True
    mock_notifier.send.assert_called_once()


@pytest.mark.anyio
async def test_notification_manager_send_exception():
    mock_notifier = AsyncMock()
    mock_notifier.send = AsyncMock(side_effect=RuntimeError("smtp fail"))
    mgr = NotificationManager.__new__(NotificationManager)
    mgr.notifiers = {"email": mock_notifier}
    result = await mgr.send("email", MagicMock())
    assert result is False


# ==================== utils/plugin_manager.py ====================


def test_plugin_manager_matched_filters_subpath_match():
    pm = PluginManager()
    filters = EventFilter(
        subpaths=["__ALL__"],
        resource_types=["__ALL__"],
        schema_shortnames=["__ALL__"],
        actions=[ActionType.create],
    )
    event = Event(
        space_name="test",
        subpath="/data",
        action_type=ActionType.create,
        resource_type=ResourceType.content,
        user_shortname="admin",
    )
    assert pm.matched_filters(filters, event) is True


def test_plugin_manager_matched_filters_subpath_no_match():
    pm = PluginManager()
    filters = EventFilter(
        subpaths=["/other"],
        resource_types=["__ALL__"],
        schema_shortnames=["__ALL__"],
        actions=[ActionType.create],
    )
    event = Event(
        space_name="test",
        subpath="/data",
        action_type=ActionType.create,
        resource_type=ResourceType.content,
        user_shortname="admin",
    )
    assert pm.matched_filters(filters, event) is False


def test_plugin_manager_matched_filters_resource_type_no_match():
    pm = PluginManager()
    filters = EventFilter(
        subpaths=["__ALL__"],
        resource_types=["folder"],
        schema_shortnames=["__ALL__"],
        actions=[ActionType.create],
    )
    event = Event(
        space_name="test",
        subpath="/data",
        action_type=ActionType.create,
        resource_type=ResourceType.content,
        schema_shortname="ticket",
        user_shortname="admin",
    )
    # resource_type is content but filter expects folder
    assert pm.matched_filters(filters, event) is False


def test_plugin_manager_matched_filters_schema_no_match():
    pm = PluginManager()
    filters = EventFilter(
        subpaths=["__ALL__"],
        resource_types=["__ALL__"],
        schema_shortnames=["other_schema"],
        actions=[ActionType.create],
    )
    event = Event(
        space_name="test",
        subpath="/data",
        action_type=ActionType.create,
        resource_type=ResourceType.content,
        schema_shortname="ticket",
        user_shortname="admin",
    )
    assert pm.matched_filters(filters, event) is False


def test_plugin_manager_sort_plugins():
    pm = PluginManager()
    filters = EventFilter(
        subpaths=["__ALL__"],
        resource_types=["__ALL__"],
        schema_shortnames=["__ALL__"],
        actions=[ActionType.create],
    )
    pw1 = PluginWrapper(
        shortname="p1", is_active=True, filters=filters, ordinal=10, listen_time=EventListenTime.before, type=PluginType.hook
    )
    pw2 = PluginWrapper(
        shortname="p2", is_active=True, filters=filters, ordinal=1, listen_time=EventListenTime.after, type=PluginType.hook
    )
    pw3 = PluginWrapper(
        shortname="p3", is_active=True, filters=filters, ordinal=5, listen_time=EventListenTime.before, type=PluginType.hook
    )
    pm.plugins_wrappers = {ActionType.create: [pw1, pw2, pw3]}
    pm.sort_plugins()

    # After sorting by ordinal
    assert pm.plugins_wrappers[ActionType.create][0].shortname == "p2"
    # Before plugins pre-computed
    assert ActionType.create in pm._before_plugins
    assert ActionType.create in pm._after_plugins


@pytest.mark.anyio
async def test_plugin_manager_before_action_no_plugins():
    pm = PluginManager()
    pm._before_plugins = {}
    event = Event(
        space_name="test",
        subpath="/data",
        action_type=ActionType.create,
        resource_type=ResourceType.content,
        user_shortname="admin",
    )
    # Should return without error
    await pm.before_action(event)


@pytest.mark.anyio
async def test_plugin_manager_after_action_space_none():
    pm = PluginManager()
    filters = EventFilter(
        subpaths=["__ALL__"],
        resource_types=["__ALL__"],
        schema_shortnames=["__ALL__"],
        actions=[ActionType.create],
    )
    pw = PluginWrapper(shortname="p1", is_active=True, filters=filters, listen_time=EventListenTime.after, type=PluginType.hook)
    pm._after_plugins = {ActionType.create: [pw]}

    event = Event(
        space_name="test",
        subpath="/data",
        action_type=ActionType.create,
        resource_type=ResourceType.content,
        user_shortname="admin",
    )
    with patch.object(PluginManager, "_get_space_cached", new_callable=AsyncMock, return_value=None):
        await pm.after_action(event)
