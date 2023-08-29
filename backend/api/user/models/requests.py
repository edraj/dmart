from enum import Enum
from typing import Dict
from pydantic import BaseModel, Field
import utils.regex as rgx
from models.api import Exception, Error


class OTPType(str, Enum):
    SMS = "SMS"
    EMAIL = "EMAIL"


class SendOTPRequest(BaseModel):
    msisdn: str | None = Field(None, pattern=rgx.MSISDN, example="7839921514")
    email: str | None = Field(None, pattern=rgx.EMAIL, example="example@gmail.com")

    def check_fields(self) -> Dict[str, str]:
        if self.email is None and self.msisdn is None:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=100,
                    message="One of these [email, msisdn] should be set!",
                ),
            )

        if [self.email, self.msisdn].count(None) != 1:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=101,
                    message="Too many input has been passed",
                ),
            )

        elif self.msisdn:
            return {"msisdn": self.msisdn}
        elif self.email:
            return {"email": self.email}

        raise Exception(
            500,
            Error(
                type="OTP",
                code=102,
                message="Something went wrong",
            ),
        )


class PasswordResetRequest(BaseModel):
    msisdn: str | None = Field(None, pattern=rgx.MSISDN, example="7839921514")
    email: str | None = Field(None, pattern=rgx.EMAIL, example="example@gmail.com")

    def check_fields(self) -> Dict[str, str]:
        if self.email is None and self.msisdn is None:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=100,
                    message="One of these [email, msisdn] should be set!",
                ),
            )

        if [self.email, self.msisdn].count(None) != 1:
            raise Exception(
                422,
                Error(
                    type="OTP",
                    code=101,
                    message="Too many input has been passed",
                ),
            )

        elif self.msisdn:
            return {"msisdn": self.msisdn}
        elif self.email:
            return {"email": self.email}

        raise Exception(
            500,
            Error(
                type="password_reset",
                code=102,
                message="Something went wrong",
            ),
        )


class ConfirmOTPRequest(SendOTPRequest, BaseModel):
    code: str = Field(..., pattern=rgx.OTP_CODE, example="165132")


class UserLoginRequest(BaseModel):
    shortname: str | None = Field(None, pattern=rgx.SHORTNAME, example="joe")
    email: str | None = Field(None, pattern=rgx.EMAIL, example="a@b.c")
    msisdn: str | None = Field(None, pattern=rgx.MSISDN, example="7812345678")
    password: str | None = Field(None, example="123")
    invitation: str | None = Field(None, pattern=rgx.INVITATION, example="abc")
    firebase_token: str | None = Field(None, example="djfb534lyb15qzdd5hbl15wjdsn")

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
