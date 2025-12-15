from typing import Dict
from pydantic import BaseModel, Field
from utils.internal_error_code import InternalErrorCode
import utils.regex as rgx
from models.api import Exception, Error
from models.enums import StrEnum


class OTPType(StrEnum):
    SMS = "SMS"
    EMAIL = "EMAIL"


class SendOTPRequest(BaseModel):
    shortname: str | None = Field(None, pattern=rgx.SHORTNAME)
    msisdn: str | None = Field(None, pattern=rgx.MSISDN)
    email: str | None = Field(None, pattern=rgx.EMAIL)

    def check_fields(self) -> Dict[str, str]:
        if self.email is None and self.msisdn is None and self.shortname is None:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=InternalErrorCode.EMAIL_OR_MSISDN_REQUIRED,
                    message="One of these [email, msisdn, shortname] should be set!",
                ),
            )

        if [self.email, self.msisdn, self.shortname].count(None) != 2:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=InternalErrorCode.INVALID_STANDALONE_DATA,
                    message="Too many input has been passed",
                ),
            )

        elif self.msisdn:
            return {"msisdn": self.msisdn}
        elif self.email:
            return {"email": self.email}
        elif self.shortname:
            return {"shortname": self.shortname}

        raise Exception(
            500,
            Error(
                type="OTP",
                code=InternalErrorCode.OTP_ISSUE,
                message="Something went wrong",
            ),
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "msisdn": "7777778110"
                }
            ]
        }
    }

class PasswordResetRequest(BaseModel):
    msisdn: str | None = Field(None, pattern=rgx.MSISDN)
    shortname: str | None = Field(None, pattern=rgx.SHORTNAME)
    email: str | None = Field(None, pattern=rgx.EMAIL)

    def check_fields(self) -> Dict[str, str]:
        if self.email is None and self.msisdn is None and self.shortname is None:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=InternalErrorCode.EMAIL_OR_MSISDN_REQUIRED,
                    message="One of these [shortname, email, msisdn] should be set!",
                ),
            )

        if [self.email, self.msisdn, self.shortname].count(None) != 2:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=InternalErrorCode.INVALID_STANDALONE_DATA,
                    message="Too many input has been passed",
                ),
            )

        elif self.msisdn:
            return {"msisdn": self.msisdn}
        elif self.email:
            return {"email": self.email}
        elif self.shortname:
            return {"shortname": self.shortname}

        raise Exception(
            500,
            Error(
                type="password_reset",
                code=InternalErrorCode.PASSWORD_RESET_ERROR,
                message="Something went wrong",
            ),
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "msisdn": "7777778110"
                }
            ]
        }
    }
class ConfirmOTPRequest(SendOTPRequest, BaseModel):
    code: str = Field(..., pattern=rgx.OTP_CODE)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "84293201"
                }
            ]
        }
    }

class UserLoginRequest(BaseModel):
    shortname: str | None = Field(None, pattern=rgx.SHORTNAME)
    email: str | None = Field(None, pattern=rgx.EMAIL)
    msisdn: str | None = Field(None, pattern=rgx.MSISDN)
    password: str | None = Field(None)
    invitation: str | None = Field(None, pattern=rgx.INVITATION)
    firebase_token: str | None = Field(None)
    otp: str | None = Field(None)

    def check_fields(self) -> Dict[str, str] | None:
        if self.shortname is None and self.email is None and self.msisdn is None:
            return {}
            # raise ValueError("One of these [shortname, email, msisdn] should be set!")

        if [self.shortname, self.email, self.msisdn].count(None) != 2:
            raise ValueError("Too many input has been passed")

        if self.shortname:
            return {"shortname": self.shortname}
        elif self.msisdn:
            return {"msisdn": self.msisdn}
        elif self.email:
            return {"email": self.email}

        return None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "shortname": "john_doo",
                    "password": "my_secure_password_@_93301"
                }
            ]
        }
    }
