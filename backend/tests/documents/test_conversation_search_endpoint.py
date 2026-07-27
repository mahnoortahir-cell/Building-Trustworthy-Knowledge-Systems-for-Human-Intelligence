from uuid import uuid4

from fastapi.testclient import TestClient


PASSWORD = "StrongPassword123!"


def register_user(
    client: TestClient,
) -> dict:
    unique_value = uuid4().hex

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Conversation Search User",
            "email": (
                f"conversation-search-{unique_value}@example.com"
            ),
            "password": PASSWORD,
            "organization_name": (
                f"Conversation Search Org {unique_value}"
            ),
        },
    )

    assert response.status_code == 201

    return response.json()


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


def conversation_search_url(
    organization_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        "/documents/conversations/search"
    )


def create_conversation(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
    title: str | None,
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


def test_search_conversations_by_title(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    matching_conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Installing NoorOS on Ubuntu",
    )

    create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Python API Architecture",
    )

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "query": "NoorOS",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["count"] == 1
    assert len(response_data["conversations"]) == 1

    result = response_data["conversations"][0]

    assert result["id"] == matching_conversation["id"]
    assert result["title"] == "Installing NoorOS on Ubuntu"


def test_search_is_case_insensitive(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Docker Compose Deployment",
    )

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "query": "docker compose",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["count"] == 1
    assert len(response_data["conversations"]) == 1
    assert (
        response_data["conversations"][0]["title"]
        == "Docker Compose Deployment"
    )


def test_search_returns_empty_collection_when_no_match(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="NoorOS Installation",
    )

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "query": "Nonexistent conversation",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversations": [],
        "count": 0,
    }


def test_search_rejects_empty_query(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "query": "   ",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "detail": (
            "Conversation search query must not be empty."
        )
    }


def test_search_requires_query_parameter(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
    )

    assert response.status_code == 422


def test_search_rejects_invalid_limit(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "query": "NoorOS",
            "limit": 101,
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "detail": (
            "Conversation search limit must not exceed 100."
        )
    }


def test_search_rejects_negative_offset(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    response = client.get(
        conversation_search_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "query": "NoorOS",
            "offset": -1,
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "detail": (
            "Conversation search offset must not be negative."
        )
    }


def test_search_requires_authentication(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]

    response = client.get(
        conversation_search_url(organization_id),
        params={
            "query": "NoorOS",
        },
    )

    assert response.status_code == 401


def test_search_does_not_return_other_organization_data(
    client: TestClient,
) -> None:
    first_registration = register_user(client)
    second_registration = register_user(client)

    first_organization_id = (
        first_registration["organization"]["id"]
    )
    second_organization_id = (
        second_registration["organization"]["id"]
    )

    first_access_token = first_registration["access_token"]
    second_access_token = second_registration["access_token"]

    create_conversation(
        client,
        organization_id=first_organization_id,
        access_token=first_access_token,
        title="Private NoorOS Conversation",
    )

    response = client.get(
        conversation_search_url(second_organization_id),
        headers=authorization_headers(second_access_token),
        params={
            "query": "Private NoorOS",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversations": [],
        "count": 0,
    }
