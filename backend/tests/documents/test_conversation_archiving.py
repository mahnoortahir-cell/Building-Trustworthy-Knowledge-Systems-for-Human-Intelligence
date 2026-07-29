from uuid import uuid4

from fastapi.testclient import TestClient


PASSWORD = "StrongPassword123!"


def register_user(
    client: TestClient,
    *,
    label: str,
) -> dict:
    unique_value = uuid4().hex

    response = client.post(
        "/auth/register",
        json={
            "full_name": f"{label} User",
            "email": f"{label.lower()}-{unique_value}@example.com",
            "password": PASSWORD,
            "organization_name": f"{label} Organization {unique_value}",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    return {
        "access_token": payload["access_token"],
        "organization_id": payload["organization"]["id"],
        "user_id": payload["user"]["id"],
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


def conversation_archive_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        f"/documents/conversations/{conversation_id}/archive"
    )


def conversation_pin_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        f"/documents/conversations/{conversation_id}/pin"
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
    title: str,
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


def archive_conversation(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
    conversation_id: str,
) -> dict:
    response = client.post(
        conversation_archive_url(
            organization_id,
            conversation_id,
        ),
        headers=authorization_headers(access_token),
    )

    assert response.status_code == 200

    return response.json()


def test_archive_sets_metadata_and_is_idempotent(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="ArchiveMetadata",
    )

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Archive metadata test",
    )

    first_response = client.post(
        conversation_archive_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert first_response.status_code == 200

    first_payload = first_response.json()

    assert first_payload["is_archived"] is True
    assert first_payload["archived_at"] is not None

    second_response = client.post(
        conversation_archive_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            registration["access_token"]
        ),
    )

    assert second_response.status_code == 200

    second_payload = second_response.json()

    assert second_payload["is_archived"] is True
    assert (
        second_payload["archived_at"]
        == first_payload["archived_at"]
    )


def test_unarchive_clears_metadata_and_is_idempotent(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="UnarchiveMetadata",
    )

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Unarchive metadata test",
    )

    archive_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        conversation_id=conversation["id"],
    )

    archive_url = conversation_archive_url(
        registration["organization_id"],
        conversation["id"],
    )

    headers = authorization_headers(
        registration["access_token"]
    )

    first_response = client.delete(
        archive_url,
        headers=headers,
    )

    assert first_response.status_code == 200

    first_payload = first_response.json()

    assert first_payload["is_archived"] is False
    assert first_payload["archived_at"] is None

    second_response = client.delete(
        archive_url,
        headers=headers,
    )

    assert second_response.status_code == 200

    second_payload = second_response.json()

    assert second_payload["is_archived"] is False
    assert second_payload["archived_at"] is None


def test_list_filters_active_archived_and_all(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="ArchiveList",
    )

    active = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Active conversation",
    )

    archived = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Archived conversation",
    )

    archive_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        conversation_id=archived["id"],
    )

    headers = authorization_headers(
        registration["access_token"]
    )

    active_response = client.get(
        conversations_url(
            registration["organization_id"]
        ),
        headers=headers,
    )

    assert active_response.status_code == 200

    active_items = active_response.json()["conversations"]

    assert [item["id"] for item in active_items] == [
        active["id"]
    ]

    archived_response = client.get(
        conversations_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "archived": "true",
        },
    )

    assert archived_response.status_code == 200

    archived_items = archived_response.json()[
        "conversations"
    ]

    assert [item["id"] for item in archived_items] == [
        archived["id"]
    ]

    all_response = client.get(
        conversations_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "archived": "all",
        },
    )

    assert all_response.status_code == 200

    all_ids = {
        item["id"]
        for item in all_response.json()["conversations"]
    }

    assert all_ids == {
        active["id"],
        archived["id"],
    }


def test_archived_pinned_conversation_is_not_in_active_list(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="ArchivedPinned",
    )

    pinned = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Pinned archived conversation",
    )

    active = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Visible active conversation",
    )

    headers = authorization_headers(
        registration["access_token"]
    )

    pin_response = client.post(
        conversation_pin_url(
            registration["organization_id"],
            pinned["id"],
        ),
        headers=headers,
    )

    assert pin_response.status_code == 200
    assert pin_response.json()["is_pinned"] is True

    archive_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        conversation_id=pinned["id"],
    )

    list_response = client.get(
        conversations_url(
            registration["organization_id"]
        ),
        headers=headers,
    )

    assert list_response.status_code == 200

    items = list_response.json()["conversations"]

    assert [item["id"] for item in items] == [
        active["id"]
    ]


def test_archived_conversation_remains_retrievable(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="ArchivedRetrievable",
    )

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Archived but retrievable",
    )

    archive_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        conversation_id=conversation["id"],
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
    assert payload["is_archived"] is True
    assert payload["archived_at"] is not None


def test_archive_enforces_organization_isolation(
    client: TestClient,
) -> None:
    owner = register_user(
        client,
        label="ArchiveOwner",
    )

    other = register_user(
        client,
        label="ArchiveOther",
    )

    conversation = create_conversation(
        client,
        organization_id=owner["organization_id"],
        access_token=owner["access_token"],
        title="Private conversation",
    )

    response = client.post(
        conversation_archive_url(
            other["organization_id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            other["access_token"]
        ),
    )

    assert response.status_code == 404


def test_search_applies_archive_filter(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="ArchiveSearch",
    )

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Unique archived research discussion",
    )

    archive_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        conversation_id=conversation["id"],
    )

    headers = authorization_headers(
        registration["access_token"]
    )

    default_response = client.get(
        conversation_search_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "query": "archived research",
        },
    )

    assert default_response.status_code == 200
    assert default_response.json()["count"] == 0

    archived_response = client.get(
        conversation_search_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "query": "archived research",
            "archived": "true",
        },
    )

    assert archived_response.status_code == 200
    assert archived_response.json()["count"] == 1
    assert (
        archived_response.json()["conversations"][0]["id"]
        == conversation["id"]
    )

    all_response = client.get(
        conversation_search_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "query": "archived research",
            "archived": "all",
        },
    )

    assert all_response.status_code == 200
    assert all_response.json()["count"] == 1


def test_invalid_archive_filter_is_rejected(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="InvalidArchiveFilter",
    )

    headers = authorization_headers(
        registration["access_token"]
    )

    list_response = client.get(
        conversations_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "archived": "invalid",
        },
    )

    assert list_response.status_code == 422

    search_response = client.get(
        conversation_search_url(
            registration["organization_id"]
        ),
        headers=headers,
        params={
            "query": "anything",
            "archived": "invalid",
        },
    )

    assert search_response.status_code == 422


def test_archived_conversation_can_be_moved_to_trash(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="DeleteArchived",
    )

    conversation = create_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        title="Delete archived conversation",
    )

    archive_conversation(
        client,
        organization_id=registration["organization_id"],
        access_token=registration["access_token"],
        conversation_id=conversation["id"],
    )

    headers = authorization_headers(
        registration["access_token"]
    )

    delete_response = client.delete(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=headers,
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        conversation_url(
            registration["organization_id"],
            conversation["id"],
        ),
        headers=headers,
    )

    assert get_response.status_code == 404
