# SkyLink Direct — API Documentation

FastAPI publishes interactive OpenAPI documentation at `http://localhost:8000/docs` and the OpenAPI JSON schema at `/openapi.json`.

Base path: `/api/v1`. Protected calls require `Authorization: Bearer <token>`. Request bodies are validated using Pydantic; invalid payloads return `422`. List endpoints return paginated envelopes `{ "items": [...], "total": int, "limit": int, "offset": int }`.

---

## 1. Authentication (`/auth`)

- `POST /auth/register`
  - Body: `{ "name": "string", "email": "user@example.com", "password": "min-10-chars" }`
  - Response (`201`): `{ "id": "uuid", "name": "...", "email": "...", "role": "user", "created_at": "ISO-8601" }`
  - Duplicate email returns `409 Conflict`.
- `POST /auth/login`
  - Body: `{ "email": "user@example.com", "password": "..." }`
  - Response (`200`): `{ "access_token": "JWT", "token_type": "bearer" }`
  - Invalid credentials return `401 Unauthorized`.
  - Rate limited to 10 attempts per minute per IP (`429 Too Many Requests`).
- `POST /auth/logout`
  - Headers: `Authorization: Bearer <token>`
  - Response (`204 No Content`): Revokes the JWT token ID (`jti`) until expiration.

---

## 2. User Profile (`/users`)

- `GET /users/me` — Retrieves current user profile (`id`, `name`, `email`, `role`, `created_at`).
- `PUT /users/me` — Update full name (`{ "name": "New Name" }`).
- `PUT /users/me/password` — Change password (`{ "current_password": "...", "new_password": "..." }`). Re-hashes with Argon2id. Returns `204`.

---

## 3. Satellites (`/satellites`)

- `GET /satellites?limit=25&offset=0` — Lists constellation satellites with orbit type, altitude (km), inclination (deg), RAAN, phase, and operational status.
- `GET /satellites/{satellite_id}` — Detailed parameters for a specific satellite.
- `GET /satellites/{satellite_id}/telemetry` — Real-time orbital propagation on WGS-84 reference ellipsoid returning current sub-satellite latitude, longitude, altitude, orbital velocity ($v \approx 7.58\text{ km/s}$), period, and ECEF coordinates.

---

## 4. Ground Stations (`/ground-stations`)

- `GET /ground-stations?limit=25&offset=0` — Lists reference ground stations with geographic coordinates and status.
- `GET /ground-stations/{station_id}` — Retrieves a specific ground station.
- `POST /ground-stations` — Administrator-only creation of ground stations (`{ "name": "...", "latitude_deg": float, "longitude_deg": float, "status": "active" }`).

---

## 5. Simulations (`/simulations`)

- `POST /simulations`
  - Body: `{ "latitude_deg": float, "longitude_deg": float }`
  - Propagates constellation orbits with Keplerian two-body solver and J2 secular perturbations to target epoch, evaluates topocentric horizon frame (East-North-Up), calculates true & apparent elevation with tropospheric refraction, Doppler shift, Free Space Path Loss (FSPL) and 3GPP NTN link budget.
  - Response (`201`): Full simulation run record with status (`visible` or `no_visibility`).
- `GET /simulations/passes?latitude_deg=float&longitude_deg=float&duration_hours=12&min_elevation_deg=10`
  - Overhead satellite pass prediction across lookahead windows (AOS, TCA, LOS, maximum elevation, and contact duration).
- `GET /simulations/{id}` — Single simulation run.
- `GET /simulations/{id}/report` — Detailed scientific link budget report including carrier frequency, FSPL, atmospheric absorption (ITU-R P.676), total path loss, $C/N_0$, SNR, apparent elevation, and 3GPP NTN throughput capacity.
- `GET /simulations/{id}/export.csv` — Downloadable RFC 4180 CSV export of simulation telemetry metrics.

---

## 6. Connections & Demo Sessions (`/connections`)

- `POST /connections`
  - Body: `{ "simulation_id": "uuid" }` or `{ "latitude_deg": float, "longitude_deg": float }`
  - Automatically transitions any previous active session to `ended` and initiates a new active session.
  - Generates initial telemetry measurements and a network event.
  - Response (`201`): `{ "id": "uuid", "satellite_id": "uuid", "satellite_name": "...", "status": "connected", "started_at": "...", "ended_at": null }`.
- `GET /connections?limit=25&offset=0` — Lists user's connection sessions ordered by most recent.
- `POST /connections/{connection_id}/end` — Concludes the specified session (`status: "ended"`).

---

## 7. Measurements and Events

- `GET /measurements?limit=25&offset=0` — Signal telemetry records (`signal_strength`, `latency_ms`, `packet_loss`, `measured_at`).
- `GET /events?limit=25&offset=0` — Audit and operational activity log (`event_type`, `description`, `created_at`).

---

## 8. Administration (`/admin`)

- `GET /admin/dashboard`
  - Protected with `require_admin` dependency (`403 Forbidden` for non-admin accounts).
  - Returns: `{ "total_users": int, "total_satellites": int, "total_simulations": int, "active_sessions": int, "network_events": int }`.

---

## 9. System Health (`/health`)

- `GET /health` — Public endpoint returning `{ "status": "ok", "connectivity": "simulation_only" }`.
