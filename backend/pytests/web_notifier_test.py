import pytest
from unittest.mock import AsyncMock, patch
from api.user.service import headers
from models.core import NotificationData, Translation, Language
from utils.sms_notifier import SMSNotifier


@pytest.mark.run(order=10)
@pytest.mark.asyncio(scope="session")
async def test_sms_notifier_send_success():
    # Arrange
    data = NotificationData(
        title=Translation(en="Title in en", ar="Title in ar"),
        body=Translation(en="Body in en", ar="Body in ar"),
        receiver={"shortname": "testuser", "language": Language.en, "msisdn": "1234567890"}
    )

    notifier = SMSNotifier()

    # Act
    with patch('api.user.service.AsyncRequest') as MockAsyncRequest:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"success": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        MockAsyncRequest.return_value.__aenter__.return_value = mock_client

        result = await notifier.send(data)

    # Assert
    assert result is True
    mock_client.post.assert_called_once_with(
        "sms/send",
        headers={**headers},
        json={"msisdn": "1234567890", "message": "Title in en"},
    )


