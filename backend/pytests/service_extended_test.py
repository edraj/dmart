"""Extended tests for api/user/service.py — covers pure functions and mockable branches."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.user.service import (
    _log_send_email_failure,
    check_user_validation,
    gen_alphanumeric,
    gen_numeric,
    get_otp_key,
    send_email,
    set_user_profile,
)
from models.core import Record, Translation, User
from models.enums import Language, ResourceType
from utils.settings import settings

# ==================== gen_numeric / gen_alphanumeric ====================


def test_gen_numeric_default_length():
    code = gen_numeric()
    assert len(code) == 6
    assert code.isdigit()


def test_gen_numeric_custom_length():
    code = gen_numeric(10)
    assert len(code) == 10
    assert code.isdigit()


def test_gen_alphanumeric_default_length():
    code = gen_alphanumeric()
    assert len(code) == 16
    assert code.isalnum()


# ==================== get_otp_key ====================


def test_get_otp_key_msisdn():
    result = get_otp_key({"msisdn": "1234567890"})
    assert result == "users:otp:otps/1234567890"


def test_get_otp_key_email():
    result = get_otp_key({"email": "test@example.com"})
    assert result == "users:otp:otps/test@example.com"


def test_get_otp_key_empty():
    result = get_otp_key({})
    assert result == ""


# ==================== check_user_validation ====================


def test_check_user_validation_email():
    user = MagicMock()
    user.email = "test@example.com"
    user.msisdn = None
    data = {"channel": "EMAIL"}
    updates: dict = {}
    token = "EMAIL:test@example.com"
    result = check_user_validation(user, data, updates, token)
    assert result.get("is_email_verified") is True


def test_check_user_validation_sms():
    user = MagicMock()
    user.email = None
    user.msisdn = "1234567890"
    data = {"channel": "SMS"}
    updates: dict = {}
    token = "SMS:1234567890"
    result = check_user_validation(user, data, updates, token)
    assert result.get("is_msisdn_verified") is True


def test_check_user_validation_no_match():
    user = MagicMock()
    user.email = "test@example.com"
    user.msisdn = None
    data = {"channel": "EMAIL"}
    updates: dict = {}
    token = "EMAIL:other@example.com"  # different email
    result = check_user_validation(user, data, updates, token)
    assert "is_email_verified" not in result


# ==================== _log_send_email_failure ====================


def test_log_send_email_failure_cancelled():
    task = MagicMock()
    task.cancelled.return_value = True
    task.exception.return_value = None
    _log_send_email_failure(task)  # should not raise


def test_log_send_email_failure_exception():
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = RuntimeError("smtp error")
    _log_send_email_failure(task)  # should not raise


def test_log_send_email_failure_success():
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = None
    _log_send_email_failure(task)  # should not raise


# ==================== send_email ====================


@pytest.mark.anyio
async def test_send_email_mock_mode():
    old_val = settings.mock_smtp_api
    settings.mock_smtp_api = True
    result = await send_email("test@example.com", "Hello", "Subject")
    assert result is True
    settings.mock_smtp_api = old_val


@pytest.mark.anyio
async def test_send_email_no_smtp_driver():
    old_mock = settings.mock_smtp_api
    old_driver = settings.mail_driver
    settings.mock_smtp_api = False
    settings.mail_driver = "none"
    result = await send_email("test@example.com", "Hello", "Subject")
    assert result is False
    settings.mail_driver = old_driver
    settings.mock_smtp_api = old_mock


@pytest.mark.anyio
async def test_send_email_creates_task():
    old_mock = settings.mock_smtp_api
    old_driver = settings.mail_driver
    old_host = settings.mail_host
    settings.mock_smtp_api = False
    settings.mail_driver = "smtp"
    settings.mail_host = "localhost"

    with patch("api.user.service._do_send_email", new_callable=AsyncMock) as mock_send:
        result = await send_email("test@example.com", "Hello", "Subject")
        assert result is True
        # Allow the background task to be created
        await asyncio.sleep(0.01)

    settings.mock_smtp_api = old_mock
    settings.mail_driver = old_driver
    settings.mail_host = old_host


# ==================== set_user_profile ====================


@pytest.mark.anyio
async def test_set_user_profile_password():
    user = User(shortname="testuser", owner_shortname="admin", password="old_hash")
    profile = Record(
        resource_type=ResourceType.user,
        shortname="testuser",
        subpath="/users",
        attributes={"password": "newpass123"},
    )
    profile_user = MagicMock()
    profile_user.password = "newpass123"
    profile_user.language = Language.en
    profile_user.is_active = True

    with patch("api.user.service.db.clear_failed_password_attempts", new_callable=AsyncMock):
        result = await set_user_profile(profile, profile_user, user)
    assert result.password != "old_hash"
    assert result.password != "newpass123"  # should be hashed
    assert result.force_password_change is False


@pytest.mark.anyio
async def test_set_user_profile_displayname_merge():
    user = User(
        shortname="testuser",
        owner_shortname="admin",
        displayname=Translation(en="Old Name"),
    )
    profile = Record(
        resource_type=ResourceType.user,
        shortname="testuser",
        subpath="/users",
        attributes={"displayname": {"ar": "Arabic Name"}},
    )
    profile_user = MagicMock()
    profile_user.password = None
    profile_user.language = Language.en
    profile_user.is_active = True

    result = await set_user_profile(profile, profile_user, user)
    # displayname should merge — result is a Translation or dict
    dn = result.displayname
    if hasattr(dn, "ar"):
        assert dn.ar == "Arabic Name"
        assert dn.en == "Old Name"
    else:
        assert dn["ar"] == "Arabic Name"  # type: ignore[index]


@pytest.mark.anyio
async def test_set_user_profile_description():
    user = User(shortname="testuser", owner_shortname="admin")
    profile = Record(
        resource_type=ResourceType.user,
        shortname="testuser",
        subpath="/users",
        attributes={"description": {"en": "New description"}},
    )
    profile_user = MagicMock()
    profile_user.password = None
    profile_user.language = Language.en
    profile_user.is_active = True

    result = await set_user_profile(profile, profile_user, user)
    desc = result.description
    if hasattr(desc, "en"):
        assert desc.en == "New description"
    else:
        assert desc == {"en": "New description"}


@pytest.mark.anyio
async def test_set_user_profile_language_and_active():
    user = User(shortname="testuser", owner_shortname="admin", language=Language.ar, is_active=False)
    profile = Record(
        resource_type=ResourceType.user,
        shortname="testuser",
        subpath="/users",
        attributes={"language": "en", "is_active": True},
    )
    profile_user = MagicMock()
    profile_user.password = None
    profile_user.language = Language.en
    profile_user.is_active = True

    result = await set_user_profile(profile, profile_user, user)
    assert result.language == Language.en
    assert result.is_active is True
