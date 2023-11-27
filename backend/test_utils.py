from fastapi import status


def check_repeated_shortname(response):
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "failed" == response.json().get("status")
    assert "request" == response.json().get("error", {}).get("type")


def check_not_found(response):
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "failed" == response.json().get("status")
    assert "db" == response.json().get("error").get("type")


def check_unauthorized(response):
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "failed" == response.json().get("status")
    assert "auth" == response.json().get("error", {}).get("type")


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
