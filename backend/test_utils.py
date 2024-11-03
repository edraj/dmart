from fastapi import status


def check_repeated_shortname(response):
    json_response = response.json()
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "failed" == json_response.get("status")
    assert "request" == json_response.get("error", {}).get("type")


def check_not_found(response):
    json_response = response.json()
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "failed" == json_response.get("status")
    assert "db" == json_response.get("error").get("type")


def check_unauthorized(response):
    json_response = response.json()
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "failed" == json_response.get("status")
    assert "auth" == json_response.get("error", {}).get("type")


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
