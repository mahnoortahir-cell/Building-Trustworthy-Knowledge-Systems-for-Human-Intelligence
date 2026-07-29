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
            "full_name": f"Soft Delete {label}",
            "email": (
                f"soft-delete-{label.lower()}-"
                f"{unique_value}@example.com"
            ),
            "password": PASSWORD,
            "organization_name": (
                f"Soft Delete {label} {unique_value}"
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


def conversation_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"{conversations_url(organization_id)}"
        f"/{conversation_id}"
    )


def restore_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"{conversation_url(organization_id, conversation_id)}"
        "/restore"
    )


def permanent_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"{conversation_url(organization_id, conversation_id)}"
        "/permanent"
    )


def archive_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"{conversation_url(organization_id, conversation_id)}"
        "/archive"
    )


def pin_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"{conversation_url(organization_id, conversation_id)}"
        "/pin"
    )


def search_url(
    organization_id: str,
) -> str:
    return (
        f"{conversations_url(organization_id)}"
        "/search"
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


def move_to_trash(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
    conversation_id: str,
) -> None:
    response = client.delete(
        conversation_url(
            organization_id,
            conversation_id,
        ),
        headers=authorization_headers(access_token),
    )

    assert response.status_code == 204


def trash_items(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
) -> list[dict]:
    response = client.get(
        conversations_url(organization_id),
        headers=authorization_headers(access_token),
        params={
            "deleted": "true",
            "archived": "all",
        },
    )

    assert response.status_code == 200

    return response.json()["conversations"]


def test_soft_delete_hides_conversation_and_exposes_metadata(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="Metadata",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Move this conversation to trash",
    )

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    headers = authorization_headers(access_token)

    get_response = client.get(
        conversation_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert get_response.status_code == 404

    active_response = client.get(
        conversations_url(organization_id),
        headers=headers,
    )

    assert active_response.status_code == 200
    assert active_response.json()["count"] == 0

    items = trash_items(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    assert len(items) == 1
    assert items[0]["id"] == conversation["id"]
    assert items[0]["is_deleted"] is True
    assert items[0]["deleted_at"] is not None


def test_soft_delete_is_idempotent(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="DeleteIdempotent",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Idempotent soft delete",
    )

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    first_deleted_at = trash_items(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )[0]["deleted_at"]

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    second_deleted_at = trash_items(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )[0]["deleted_at"]

    assert second_deleted_at == first_deleted_at


def test_restore_is_idempotent(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="RestoreIdempotent",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Restore this conversation",
    )

    headers = authorization_headers(access_token)
    url = restore_url(
        organization_id,
        conversation["id"],
    )

    active_restore = client.post(
        url,
        headers=headers,
    )

    assert active_restore.status_code == 200
    assert active_restore.json()["is_deleted"] is False

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    first_restore = client.post(
        url,
        headers=headers,
    )

    assert first_restore.status_code == 200
    assert first_restore.json()["is_deleted"] is False
    assert first_restore.json()["deleted_at"] is None

    second_restore = client.post(
        url,
        headers=headers,
    )

    assert second_restore.status_code == 200
    assert second_restore.json()["is_deleted"] is False


def test_restore_preserves_pin_and_archive_state(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="PreserveState",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Preserve lifecycle state",
    )

    headers = authorization_headers(access_token)

    pin_response = client.post(
        pin_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert pin_response.status_code == 200

    archive_response = client.post(
        archive_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert archive_response.status_code == 200

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    restore_response = client.post(
        restore_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert restore_response.status_code == 200

    restored = restore_response.json()

    assert restored["is_deleted"] is False
    assert restored["is_pinned"] is True
    assert restored["pinned_at"] is not None
    assert restored["is_archived"] is True
    assert restored["archived_at"] is not None

    active_response = client.get(
        conversations_url(organization_id),
        headers=headers,
    )

    assert active_response.status_code == 200
    assert active_response.json()["count"] == 0

    archived_response = client.get(
        conversations_url(organization_id),
        headers=headers,
        params={
            "archived": "true",
        },
    )

    assert archived_response.status_code == 200
    assert archived_response.json()["count"] == 1


def test_deleted_conversation_is_read_only(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="ReadOnly",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Deleted conversations are read only",
    )

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    headers = authorization_headers(access_token)

    update_response = client.patch(
        conversation_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
        json={
            "title": "This update must fail",
        },
    )

    assert update_response.status_code == 404

    pin_response = client.post(
        pin_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert pin_response.status_code == 404

    archive_response = client.post(
        archive_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert archive_response.status_code == 404


def test_list_and_search_apply_deleted_filter(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="Filters",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    active = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Active lifecycle discussion",
    )

    deleted = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Unique deleted lifecycle discussion",
    )

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=deleted["id"],
    )

    headers = authorization_headers(access_token)

    active_list = client.get(
        conversations_url(organization_id),
        headers=headers,
    )

    assert active_list.status_code == 200
    assert [
        item["id"]
        for item in active_list.json()["conversations"]
    ] == [active["id"]]

    deleted_list = client.get(
        conversations_url(organization_id),
        headers=headers,
        params={
            "deleted": "true",
            "archived": "all",
        },
    )

    assert deleted_list.status_code == 200
    assert [
        item["id"]
        for item in deleted_list.json()["conversations"]
    ] == [deleted["id"]]

    all_list = client.get(
        conversations_url(organization_id),
        headers=headers,
        params={
            "deleted": "all",
            "archived": "all",
        },
    )

    assert all_list.status_code == 200
    assert {
        item["id"]
        for item in all_list.json()["conversations"]
    } == {
        active["id"],
        deleted["id"],
    }

    default_search = client.get(
        search_url(organization_id),
        headers=headers,
        params={
            "query": "unique deleted lifecycle",
        },
    )

    assert default_search.status_code == 200
    assert default_search.json()["count"] == 0

    deleted_search = client.get(
        search_url(organization_id),
        headers=headers,
        params={
            "query": "unique deleted lifecycle",
            "deleted": "true",
            "archived": "all",
        },
    )

    assert deleted_search.status_code == 200
    assert deleted_search.json()["count"] == 1
    assert (
        deleted_search.json()["conversations"][0]["id"]
        == deleted["id"]
    )


def test_invalid_deleted_filter_is_rejected(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="InvalidFilter",
    )

    organization_id = registration["organization"]["id"]
    headers = authorization_headers(
        registration["access_token"]
    )

    list_response = client.get(
        conversations_url(organization_id),
        headers=headers,
        params={
            "deleted": "invalid",
        },
    )

    assert list_response.status_code == 422

    search_response = client.get(
        search_url(organization_id),
        headers=headers,
        params={
            "query": "anything",
            "deleted": "invalid",
        },
    )

    assert search_response.status_code == 422


def test_permanent_delete_requires_trash(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="PermanentConflict",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Permanent delete requires trash",
    )

    response = client.delete(
        permanent_url(
            organization_id,
            conversation["id"],
        ),
        headers=authorization_headers(access_token),
    )

    assert response.status_code == 409


def test_permanent_delete_removes_trashed_conversation(
    client: TestClient,
) -> None:
    registration = register_user(
        client,
        label="Permanent",
    )

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
        title="Permanently delete this conversation",
    )

    move_to_trash(
        client,
        organization_id=organization_id,
        access_token=access_token,
        conversation_id=conversation["id"],
    )

    headers = authorization_headers(access_token)

    delete_response = client.delete(
        permanent_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert delete_response.status_code == 204

    restore_response = client.post(
        restore_url(
            organization_id,
            conversation["id"],
        ),
        headers=headers,
    )

    assert restore_response.status_code == 404

    assert trash_items(
        client,
        organization_id=organization_id,
        access_token=access_token,
    ) == []


def test_soft_delete_enforces_organization_isolation(
    client: TestClient,
) -> None:
    owner = register_user(
        client,
        label="Owner",
    )

    other = register_user(
        client,
        label="Other",
    )

    conversation = create_conversation(
        client,
        organization_id=owner["organization"]["id"],
        access_token=owner["access_token"],
        title="Private lifecycle conversation",
    )

    response = client.delete(
        conversation_url(
            other["organization"]["id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            other["access_token"]
        ),
    )

    assert response.status_code == 404

    restore_response = client.post(
        restore_url(
            other["organization"]["id"],
            conversation["id"],
        ),
        headers=authorization_headers(
            other["access_token"]
        ),
    )

    assert restore_response.status_code == 404
