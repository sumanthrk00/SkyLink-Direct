# API documentation

FastAPI publishes interactive OpenAPI at `http://localhost:8000/docs` and the JSON schema at `/openapi.json`.

Base path: `/api/v1`. Protected calls require `Authorization: Bearer <token>`. Request bodies are validated with Pydantic; invalid payloads return `422`. Lists return `{ "items": [], "total": 0, "limit": 25, "offset": 0 }`.

## Authentication

- `POST /auth/register` — `{ "name": "Demo User", "email": "user@example.com", "password": "at-least-10-chars" }`; creates a regular user (`201`). Duplicate email: `409`.
- `POST /auth/login` — `{ "email": "user@example.com", "password": "..." }`; returns a bearer token. Invalid credentials: `401`.
- `POST /auth/logout` — revokes the current token (`204`).

## User and inventory

- `GET /users/me` — current profile.
- `PUT /users/me` — `{ "name": "Updated name" }`.
- `PUT /users/me/password` — `{ "current_password": "...", "new_password": "at-least-10-chars" }`; verifies the current password and replaces the Argon2 hash.
- `GET /satellites?limit=50&offset=0`, `GET /satellites/{uuid}` — demo inventory.

## Simulation and sessions

- `POST /simulations` — `{ "latitude_deg": 12.97, "longitude_deg": 77.59 }`; stores the best geometric estimate, labelled `illustrative_estimate`.
- `GET /simulations?limit=25&offset=0`, `GET /simulations/{uuid}` — caller's history.
- `POST /connections` — `{ "simulation_id": "uuid" }` or a latitude/longitude pair; starts one demo session if visible.
- `GET /connections?limit=25&offset=0`, `POST /connections/{uuid}/end` — caller's sessions and termination.
- `GET /measurements?limit=25&offset=0`, `GET /events?limit=25&offset=0` — caller's histories.

## Administration

- `GET /admin/dashboard` — account, satellite, simulation, session and event counts. Requires an existing admin; public signup cannot create one.

`200` indicates successful read/update; `201` creation; `204` logout; `401` missing/invalid/revoked auth; `403` insufficient role; `404` missing or non-owned resource; `409` conflict; `422` invalid payload; `429` authentication rate limit. Geometric visibility does not imply a real radio link.
