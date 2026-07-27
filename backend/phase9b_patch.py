from pathlib import Path
import re, shutil

root = Path.cwd()
schema = root/'app/documents/conversation_schemas.py'
router = root/'app/documents/router.py'
tests = root/'tests/documents/test_conversation_endpoints.py'
readme = root.parent/'README.md'
backup = root/'.phase9b_backup'

for p in (schema, router, tests, readme):
    if not p.exists():
        raise SystemExit(f'Missing required file: {p}')

if backup.exists(): shutil.rmtree(backup)
backup.mkdir()
for p in (schema, router, tests, readme):
    target = backup / (p.name if p == readme else p.relative_to(root))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target)

def rw(path, transform):
    old = path.read_text(encoding='utf-8')
    new = transform(old)
    path.write_text(new, encoding='utf-8', newline='\n')


def patch_schema(text):
    if 'is_pinned: bool' in text:
        return text
    m = re.search(r'class ConversationResponse\([^)]+\):(?P<body>.*?)(?=\nclass |\Z)', text, re.S)
    if not m: raise RuntimeError('ConversationResponse not found')
    block = m.group(0)
    t = re.search(r'(?m)^(\s+title:\s*str\s*\|\s*None[^\n]*\n)', block)
    if not t: raise RuntimeError('ConversationResponse.title not found')
    block = block[:t.end()] + '    is_pinned: bool\n    pinned_at: datetime | None\n' + block[t.end():]
    return text[:m.start()] + block + text[m.end():]


def patch_router(text):
    for name in ('pin_document_conversation','unpin_document_conversation'):
        if re.search(rf'\b{name}\b', text):
            continue
        m = re.search(r'from app\.documents\.conversation_service import \((?P<body>.*?)\n\)', text, re.S)
        if not m: raise RuntimeError('conversation_service import block not found')
        body = m.group('body') + f'\n    {name},'
        text = text[:m.start('body')] + body + text[m.end('body'):]
    if '"/conversations/{conversation_id}/pin"' in text:
        return text
    endpoint = '''@router.post(
    "/conversations/{conversation_id}/pin",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
def pin_conversation(
    conversation_id: str,
    membership: Annotated[Membership, Depends(get_current_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationResponse:
    try:
        conversation = pin_document_conversation(
            db,
            organization_id=membership.organization_id,
            conversation_id=conversation_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationPersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}/pin",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
def unpin_conversation(
    conversation_id: str,
    membership: Annotated[Membership, Depends(get_current_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationResponse:
    try:
        conversation = unpin_document_conversation(
            db,
            organization_id=membership.organization_id,
            conversation_id=conversation_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationPersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ConversationResponse.model_validate(conversation)


'''
    m = re.search(r'@router\.delete\(\s*\n\s*"/conversations/\{conversation_id\}"', text)
    if not m: raise RuntimeError('delete endpoint marker not found')
    return text[:m.start()] + endpoint + text[m.start():]


def patch_tests(text):
    if 'def conversation_pin_url(' not in text:
        marker = text.find('def create_conversation(')
        if marker < 0: raise RuntimeError('create_conversation helper not found')
        helper = '''def conversation_pin_url(organization_id: str, conversation_id: str) -> str:\n    return (f"/organizations/{organization_id}"\n            f"/documents/conversations/{conversation_id}/pin")\n\n\n'''
        text = text[:marker] + helper + text[marker:]
    if 'def test_pin_conversation_sets_pin_metadata(' in text:
        return text
    block = '''\n\ndef test_pin_conversation_sets_pin_metadata(client: TestClient) -> None:\n    registration = register_user(client)\n    conversation = create_conversation(client, organization_id=registration["organization_id"], access_token=registration["access_token"])\n    response = client.post(conversation_pin_url(registration["organization_id"], conversation["id"]), headers=authorization_headers(registration["access_token"]))\n    assert response.status_code == 200\n    assert response.json()["is_pinned"] is True\n    assert response.json()["pinned_at"] is not None\n\n\ndef test_unpin_conversation_clears_pin_metadata(client: TestClient) -> None:\n    registration = register_user(client)\n    conversation = create_conversation(client, organization_id=registration["organization_id"], access_token=registration["access_token"])\n    url = conversation_pin_url(registration["organization_id"], conversation["id"])\n    headers = authorization_headers(registration["access_token"])\n    assert client.post(url, headers=headers).status_code == 200\n    response = client.delete(url, headers=headers)\n    assert response.status_code == 200\n    assert response.json()["is_pinned"] is False\n    assert response.json()["pinned_at"] is None\n\n\ndef test_pinned_conversation_appears_first(client: TestClient) -> None:\n    registration = register_user(client)\n    pinned = create_conversation(client, organization_id=registration["organization_id"], access_token=registration["access_token"], title="Pinned")\n    headers = authorization_headers(registration["access_token"])\n    assert client.post(conversation_pin_url(registration["organization_id"], pinned["id"]), headers=headers).status_code == 200\n    unpinned = create_conversation(client, organization_id=registration["organization_id"], access_token=registration["access_token"], title="Unpinned")\n    response = client.get(conversations_url(registration["organization_id"]), headers=headers)\n    assert response.status_code == 200\n    items = response.json()["conversations"]\n    assert items[0]["id"] == pinned["id"]\n    assert items[1]["id"] == unpinned["id"]\n'''
    return text.rstrip() + block + '\n'


def patch_readme(text):
    if '## Conversation Pinning' in text:
        return text
    return text.rstrip() + '''\n\n## Conversation Pinning\n\nNoorOS supports organisation-scoped pinning and unpinning of document conversations. Conversation responses include `is_pinned` and `pinned_at`, and pinned conversations are prioritised in list and search results.\n'''

rw(schema, patch_schema)
rw(router, patch_router)
rw(tests, patch_tests)
rw(readme, patch_readme)
print('Phase 9B source patch completed.')
print(f'Backup: {backup}')
