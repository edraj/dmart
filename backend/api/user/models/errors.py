from models.api import Error

INVALID_OTP = Error(
    type="OTP",
    code=307,
    message="Invalid OTP",
)

EXPIRED_OTP = Error(
    type="OTP",
    code=308,
    message="Expired OTP",
)
