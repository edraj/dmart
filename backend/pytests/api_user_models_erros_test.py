import pytest
from models.api import Error
from utils.internal_error_code import InternalErrorCode
from api.user.model.errors import INVALID_OTP, EXPIRED_OTP

def test_invalid_otp():
    assert isinstance(INVALID_OTP, Error)
    assert INVALID_OTP.type == "OTP"
    assert INVALID_OTP.code == InternalErrorCode.OTP_INVALID
    assert INVALID_OTP.message == "Invalid OTP"

def test_expired_otp():
    assert isinstance(EXPIRED_OTP, Error)
    assert EXPIRED_OTP.type == "OTP"
    assert EXPIRED_OTP.code == InternalErrorCode.OTP_EXPIRED
    assert EXPIRED_OTP.message == "Expired OTP"