from models.api import Error
from utils.internal_error_code import InternalErrorCode

INVALID_OTP = Error(
    type="OTP",
    code=InternalErrorCode.OTP_INVALID,
    message="Invalid OTP",
)

EXPIRED_OTP = Error(
    type="OTP",
    code=InternalErrorCode.OTP_EXPIRED,
    message="Expired OTP",
)
