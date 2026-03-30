from fastapi import status


def check_repeated_shortname(response):
    json_response = response.json()
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert json_response.get("status") == "failed"
    assert json_response.get("error", {}).get("type") == "request"


def check_not_found(response):
    json_response = response.json()
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert json_response.get("status") == "failed"
    assert json_response.get("error").get("type") == "db"


def check_unauthorized(response):
    json_response = response.json()
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert json_response.get("status") == "failed"
    assert json_response.get("error", {}).get("type") == "auth"


def assert_code_and_status_success(response):
    if response.status_code != status.HTTP_200_OK:
        print(
            "\n\n\n\n\n========================= ERROR RESPONSE: =========================n:",
            response.json(),
            "\n\n\n\n\n",
        )
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["status"] == "success"
