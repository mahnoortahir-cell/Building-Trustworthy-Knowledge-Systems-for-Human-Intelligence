# NoorOS Backend

FastAPI backend for NoorOS, a trustworthy organisation-scoped knowledge system.

## Status

- PostgreSQL and SQLAlchemy integration
- Alembic migrations
- pgvector embeddings and semantic retrieval
- JWT registration, login, and current-user flow
- Role and organisation-based authorisation
- PDF upload, extraction, versioning, chunking, and embedding
- Grounded RAG answers with citations
- Server-Sent Events streaming and cancellation
- Conversation persistence, memory, titles, search, and regeneration
- Pin, archive, soft delete, restore, and permanent delete
- Test suite: **290 passed, 13 deprecation warnings, 0 failures**
- Migration head: `e7b1d9f4a2c8`

## Technology

Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pgvector, JWT, Pytest, and Server-Sent Events.

## Authentication

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Protected resources are organisation-scoped. Users can access only resources belonging to organisations where they have authorised membership.

## Organisations

- `POST /organizations`
- `GET /organizations`
- `GET /organizations/{organization_id}`

Organisation isolation applies to documents, chunks, searches, conversations, messages, and generated answers.

## Documents and Retrieval

The document pipeline supports PDF upload, local storage, extraction, versioning, chunking, embedding generation, vector storage, and organisation-scoped semantic search.

## Grounded Answers

NoorOS retrieves evidence from trusted documents before generating an answer. Current capabilities include citations, conversation-aware context, regeneration, streaming, and cancellation.

## Conversation Lifecycle

The backend supports creation, listing, title editing, search, pinning, archiving, soft deletion, restoration, and permanent deletion.

Archive and deletion states are independent. Soft deletion preserves messages and metadata. Permanently deleting a conversation is allowed only after soft deletion and cascades to its messages.

Deleted conversations are hidden from normal read, update, pin, archive, answer, stream, and regenerate operations.

## API Documentation

- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- Health: `http://127.0.0.1:8000/health`

## Local Development

From the repository root:

1. Activate the environment: `.\.venv\Scripts\Activate.ps1`
2. Enter the backend: `Set-Location .\backend`
3. Apply migrations: `alembic upgrade head`
4. Start the API: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
5. Run tests: `pytest`

When port 8000 is already occupied, check `Invoke-RestMethod http://127.0.0.1:8000/health`. A healthy response means the backend is already running.

## Frontend Integration

During development, Vite proxies `/api/*` to `http://127.0.0.1:8000/*`. The frontend currently has a reusable API client, JWT-ready requests, Zustand authentication state, a successful health connection, and a passing production build.

## Remaining Roadmap

- Conversation metadata and advanced filters
- Export and audit logging
- Background jobs and Redis-backed cancellation
- Refresh tokens, revocation, password reset, and email verification
- Rate limiting, security headers, and production CORS
- Object storage, monitoring, CI/CD, deployment hardening
- Load and performance testing
