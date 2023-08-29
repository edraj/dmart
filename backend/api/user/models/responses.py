from pydantic import BaseModel, Field

from models.api import Response


class Confirmation(BaseModel):
    confirmation: str = Field(...)


class ConfirmationResponse(Response):
    data: Confirmation
