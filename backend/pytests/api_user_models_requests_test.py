import pytest
from pydantic import ValidationError

from api.user.model.requests import (
    OTPType,
    SendOTPRequest,
    PasswordResetRequest,
    ConfirmOTPRequest,
    UserLoginRequest,
    Exception,
    Error,
    InternalErrorCode
)
import utils.regex as rgx


def test_send_otp_request_valid_msisdn():
    request = SendOTPRequest(msisdn="7777778110")
    result = request.check_fields()
    assert result == {"msisdn": "7777778110"}

def test_send_otp_request_valid_email():
    request = SendOTPRequest(email="test@example.com")
    result = request.check_fields()
    assert result == {"email": "test@example.com"}

def test_send_otp_request_missing_fields():
    # Ensure both fields are explicitly None
    with pytest.raises(Exception) as excinfo:
        SendOTPRequest(msisdn=None, email=None).check_fields()
    assert excinfo.value.status_code == 422
    assert excinfo.value.error.code == InternalErrorCode.EMAIL_OR_MSISDN_REQUIRED

def test_send_otp_request_too_many_fields():
    with pytest.raises(Exception) as excinfo:
        SendOTPRequest(msisdn="7777778110", email="test@example.com").check_fields()
    assert excinfo.value.status_code == 422
    assert excinfo.value.error.code == InternalErrorCode.INVALID_STANDALONE_DATA

def test_password_reset_request_valid_msisdn():
    request = PasswordResetRequest(msisdn="7777778110")
    result = request.check_fields()
    assert result == {"msisdn": "7777778110"}

def test_password_reset_request_valid_email():
    request = PasswordResetRequest(email="test@example.com")
    result = request.check_fields()
    assert result == {"email": "test@example.com"}

def test_password_reset_request_missing_fields():
    with pytest.raises(Exception) as excinfo:
        PasswordResetRequest().check_fields()
    assert excinfo.value.status_code == 422
    assert excinfo.value.error.code == InternalErrorCode.EMAIL_OR_MSISDN_REQUIRED

def test_password_reset_request_too_many_fields():
    with pytest.raises(Exception) as excinfo:
        PasswordResetRequest(msisdn="7777778110", email="test@example.com").check_fields()
    assert excinfo.value.status_code == 422
    assert excinfo.value.error.code == InternalErrorCode.INVALID_STANDALONE_DATA

def test_confirm_otp_request_valid():
    request = ConfirmOTPRequest(msisdn="7777778110", code="123456")
    assert request.msisdn == "7777778110"
    assert request.code == "123456"

def test_confirm_otp_request_invalid_code():
    with pytest.raises(ValidationError):
        ConfirmOTPRequest(msisdn="7777778110", code="invalid")

def test_user_login_request_valid_shortname():
    request = UserLoginRequest(shortname="john_doo", password="my_secure_password_@_93301")
    result = request.check_fields()
    assert result == {"shortname": "john_doo"}

def test_user_login_request_valid_email():
    request = UserLoginRequest(email="test@example.com", password="my_secure_password_@_93301")
    result = request.check_fields()
    assert result == {"email": "test@example.com"}

def test_user_login_request_valid_msisdn():
    request = UserLoginRequest(msisdn="7777778110", password="my_secure_password_@_93301")
    result = request.check_fields()
    assert result == {"msisdn": "7777778110"}

def test_user_login_request_missing_fields():
    request = UserLoginRequest(password="my_secure_password_@_93301")
    result = request.check_fields()
    assert result == {}

def test_user_login_request_too_many_fields():
    with pytest.raises(ValueError, match="Too many input has been passed"):
        UserLoginRequest(shortname="john_doo", email="test@example.com", msisdn="7777778110", password="my_secure_password_@_93301").check_fields()

def test_user_login_request_missing_password():
    request = UserLoginRequest(shortname="john_doo")
    result = request.check_fields()
    assert result == {"shortname": "john_doo"}