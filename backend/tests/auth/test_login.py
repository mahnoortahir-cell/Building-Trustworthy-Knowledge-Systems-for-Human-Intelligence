from fastapi.testclient import TestClient


def create_user(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "full_name": "Login User",
            "email": "login@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Login Organization",
        },
    )


def test_login_success(client: TestClient):
    create_user(client)

    response = client.post(
        "/auth/login",
        data={
            "username": "login@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client: TestClient):
    create_user(client)

    response = client.post(
        "/auth/login",
        data={
            "username": "login@example.com",
            "password": "WrongPassword",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Incorrect email or password."
    }