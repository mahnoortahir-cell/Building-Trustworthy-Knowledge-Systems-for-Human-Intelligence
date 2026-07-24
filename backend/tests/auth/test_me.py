from fastapi.testclient import TestClient


def register_and_login(client: TestClient) -> str:
    client.post(
        "/auth/register",
        json={
            "full_name": "Protected User",
            "email": "protected@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Protected Org",
        },
    )

    login_response = client.post(
        "/auth/login",
        data={
            "username": "protected@example.com",
            "password": "StrongPassword123!",
        },
    )

    return login_response.json()["access_token"]


def test_get_current_user(client: TestClient):
    token = register_and_login(client)

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["email"] == "protected@example.com"
    assert body["full_name"] == "Protected User"
    assert body["is_active"] is True
    assert len(body["organizations"]) == 1
    assert body["organizations"][0]["role"] == "owner"


def test_get_current_user_without_token(client: TestClient):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_get_current_user_invalid_token(client: TestClient):
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401