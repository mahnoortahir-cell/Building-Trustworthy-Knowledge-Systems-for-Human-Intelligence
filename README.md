"# Building-Trustworthy-Knowledge-Systems-for-Human-Intelligence"

## Conversation Pinning

NoorOS supports organisation-scoped pinning and unpinning of document conversations. Conversation responses include `is_pinned` and `pinned_at`, and pinned conversations are prioritised in list and search results.

<!-- FRONTEND_AUTH_STATUS_START -->
## Frontend Authentication Status

The NoorOS frontend now includes a working authentication milestone connected to the FastAPI backend.

Implemented:

- React and TypeScript authentication pages
- User registration through `POST /auth/register`
- User login through `POST /auth/login`
- Current-user loading through `GET /auth/me`
- JWT-aware API requests
- Persistent authentication state with Zustand
- Protected routing for authenticated pages
- Authenticated dashboard
- Logout and session clearing
- Redirect back to the requested protected route after login
- Responsive authentication and dashboard styling

Validation completed:

- Login works against the local FastAPI backend
- Registration works against the local FastAPI backend
- Protected dashboard opens after authentication
- Frontend production build passes
- Frontend lint passes
- Backend health endpoint reports `healthy`

The next frontend milestone is the organisation document library and PDF upload workflow.
<!-- FRONTEND_AUTH_STATUS_END -->

## Database-Backed Document Library

NoorOS now includes a permanent organisation-scoped document library with PDF upload, PostgreSQL listing, newest-first ordering, pagination, automatic frontend refresh, and semantic-search filtering.

