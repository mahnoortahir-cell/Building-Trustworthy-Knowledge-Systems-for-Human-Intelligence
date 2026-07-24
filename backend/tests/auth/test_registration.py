from fastapi.testclient import TestClient


def test_register_user_successfully(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Test Organization",
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["token_type"] == "bearer"
    assert response_data["access_token"]
    assert response_data["role"] == "owner"

    assert response_data["user"]["full_name"] == "Test User"
    assert response_data["user"]["email"] == "test@example.com"
    assert response_data["user"]["is_active"] is True

    assert response_data["organization"]["name"] == "Test Organization"
    assert response_data["organization"]["slug"] == "test-organization"

def test_register_duplicate_email_returns_conflict(
    client: TestClient,
) -> None:
    payload = {
        "full_name": "Test User",
        "email": "duplicate@example.com",
        "password": "StrongPassword123!",
        "organization_name": "Test Organization",
    }

    first_response = client.post(
        "/auth/register",
        json=payload,
    )

    second_response = client.post(
        "/auth/register",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "An account with this email already exists."
    }    