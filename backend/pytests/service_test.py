from api.user.service import mock_sending_otp, gen_alphanumeric, send_otp
import pytest




@pytest.mark.run(order=9)
def test_gen_alphanumeric_length():
    # Test default length
    result = gen_alphanumeric()
    assert len(result) == 16, "Default length should be 16"

    # Test custom length
    length = 32
    result = gen_alphanumeric(length)
    assert len(result) == length, f"Length should be {length}"


@pytest.mark.run(order=9)
def test_gen_alphanumeric_characters():
    result = gen_alphanumeric()
    assert all(c.isalnum() for c in result), "Result should only contain alphanumeric characters"


@pytest.mark.run(order=9)
def test_gen_alphanumeric_unique():
    num_samples = 100
    samples = {gen_alphanumeric() for _ in range(num_samples)}
    assert len(samples) == num_samples, "Generated strings should be unique"

# @pytest.mark.run(order=9)
# @pytest.mark.asyncio(scope="session")
# async def test_Mock_send_otp():
#     # arrange
#     msisdn = "07832020366"
#
#     # act
#     result = await mock_sending_otp(msisdn)
#
#     # assert
#     assert result == {"status": "success", "data": {"status": "success"}}
#
#
# class MockSettings:
#     mock_smpp_api = True
#     otp_token_ttl = 300
#     comms_api = ""


# @pytest.mark.run(order=9)
# @pytest.mark.asyncio(scope="session")
# async def test_send_otp_with_mock_sending_otp(mocker):
#     # Mock the settings
#     mocker.patch('utils.settings', MockSettings)
#
#     # Define the msisdn and language for testing
#     msisdn = "1234567890"
#     language = "en"
#
#     # Call the send_otp function
#     result = await send_otp(msisdn, language)
#
#     # Assert the result
#     assert result == {"status": "success"}

