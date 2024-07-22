import pytest
from pydantic import BaseModel, Field, ValidationError
from models.api import Response
from api.user.models.responses import Confirmation, \
    ConfirmationResponse  # Replace 'your_module' with the actual module name where Confirmation and ConfirmationResponse are defined


def test_confirmation_model():
    confirmation_instance = Confirmation(confirmation="confirmed")
    assert isinstance(confirmation_instance, Confirmation)
    assert confirmation_instance.confirmation == "confirmed"

    with pytest.raises(ValidationError):
        # This should raise a ValidationError because 'confirmation' is required
        Confirmation()


def test_confirmation_response_model():
    confirmation_instance = Confirmation(confirmation="confirmed")
    response_instance = ConfirmationResponse(status="success", data=confirmation_instance)

    assert isinstance(response_instance, ConfirmationResponse)
    assert response_instance.status == "success"
    assert response_instance.data == confirmation_instance
    assert response_instance.data.confirmation == "confirmed"

    with pytest.raises(ValidationError):
        # This should raise a ValidationError because 'data' is required
        ConfirmationResponse(status="success")

    with pytest.raises(ValidationError):
        # This should raise a ValidationError because 'status' is required
        ConfirmationResponse(data=confirmation_instance)

    with pytest.raises(ValidationError):
        # This should raise a ValidationError because 'data' must be a Confirmation instance
        ConfirmationResponse(status="success", data="not a Confirmation instance")


