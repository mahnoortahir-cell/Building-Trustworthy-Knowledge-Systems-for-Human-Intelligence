import time
from datetime import datetime

from fastapi.testclient import TestClient


def register_user(
    client: TestClient,
    *,
    email: str = "conversation-user@example.com",
    organization_name: str = "Conversation Organization",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Conversation Test User",
            "email": email,
            "password": "StrongPassword123!",
            "organization_name": organization_name,
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    return {
        "access_token": response_data["access_token"],
        "organization_id": response_data["organization"]["id"],
        "user_id": response_data["user"]["id"],
    }


def authorization_headers(
    access_token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def conversations_url(
    organization_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        "/documents/conversations"
    )


def conversation_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        f"/documents/conversations/{conversation_id}"
    )


def create_conversation(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
    title: str | None = "Test Conversation",
) -> dict:
    response = client.post(
        conversations_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "title": title,
        },
    )

    assert response.status_code == 201

    return response.json()


def test_create_conversation_returns_created_resource(
    client: TestClient,
) -> None:
    registration = register_user(client)

    response = client.post(
        conversations_url(registration["organization_id"]),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Project Noor",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["id"]
    assert (
        payload["organization_id"]
        == registration["organization_id"]
    )
    assert payload["title"] == "Project Noor"
    assert payload["created_at"]
    assert payload["updated_at"]


def test_create_conversation_normalizes_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="   Project     Noor   Architecture   ",
    )

    assert conversation["title"] == "Project Noor Architecture"


def test_list_conversations_returns_created_conversation(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    response = client.get(
        conversations_url(registration["organization_id"]),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1
    assert len(payload["conversations"]) == 1
    assert payload["conversations"][0]["id"] == conversation["id"]


def test_get_conversation_returns_empty_message_history(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    response = client.get(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == conversation["id"]
    assert payload["title"] == "Test Conversation"
    assert payload["messages"] == []


def test_update_conversation_changes_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Original Title",
    )

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Updated Title",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == conversation["id"]
    assert payload["title"] == "Updated Title"
    assert (
        payload["organization_id"]
        == registration["organization_id"]
    )


def test_update_conversation_changes_updated_at(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    original_updated_at = datetime.fromisoformat(
        conversation["updated_at"].replace("Z", "+00:00")
    )

    time.sleep(0.01)

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Timestamp Updated",
        },
    )

    assert response.status_code == 200

    updated_at = datetime.fromisoformat(
        response.json()["updated_at"].replace("Z", "+00:00")
    )

    assert updated_at > original_updated_at


def test_update_conversation_normalizes_whitespace(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "   Project      Noor     Research   ",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Project Noor Research"


def test_update_conversation_with_null_clears_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Temporary Title",
    )

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] is None


def test_update_conversation_with_whitespace_clears_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Temporary Title",
    )

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "       ",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] is None


def test_update_conversation_rejects_missing_title_field(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={},
    )

    assert response.status_code == 422


def test_update_conversation_rejects_title_over_255_characters(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "x" * 256,
        },
    )

    assert response.status_code == 422


def test_update_unknown_conversation_returns_not_found(
    client: TestClient,
) -> None:
    registration = register_user(client)

    response = client.patch(
        conversation_url(
            registration["organization_id"],
            "missing-conversation-id",
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Updated Title",
        },
    )

    assert response.status_code == 404


def test_get_conversation_reflects_updated_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    update_response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Updated Detail Title",
        },
    )

    assert update_response.status_code == 200

    get_response = client.get(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert get_response.status_code == 200
    assert (
        get_response.json()["title"]
        == "Updated Detail Title"
    )


def test_list_conversations_reflects_updated_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    update_response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Updated List Title",
        },
    )

    assert update_response.status_code == 200

    list_response = client.get(
        conversations_url(registration["organization_id"]),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert list_response.status_code == 200

    conversations = list_response.json()["conversations"]

    assert len(conversations) == 1
    assert conversations[0]["title"] == "Updated List Title"


def test_delete_conversation_removes_resource(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    delete_response = client.delete(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert get_response.status_code == 404


def test_update_deleted_conversation_returns_not_found(
    client: TestClient,
) -> None:
    registration = register_user(client)

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
    )

    delete_response = client.delete(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert delete_response.status_code == 204

    update_response = client.patch(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
        json={
            "title": "Cannot Update",
        },
    )

    assert update_response.status_code == 404


def test_list_conversations_rejects_invalid_pagination(
    client: TestClient,
) -> None:
    registration = register_user(client)

    headers = authorization_headers(
        registration["access_token"]
    )
    url = conversations_url(registration["organization_id"])

    zero_limit_response = client.get(
        url,
        headers=headers,
        params={
            "limit": 0,
        },
    )

    excessive_limit_response = client.get(
        url,
        headers=headers,
        params={
            "limit": 101,
        },
    )

    negative_offset_response = client.get(
        url,
        headers=headers,
        params={
            "offset": -1,
        },
    )

    assert zero_limit_response.status_code == 422
    assert excessive_limit_response.status_code == 422
    assert negative_offset_response.status_code == 422