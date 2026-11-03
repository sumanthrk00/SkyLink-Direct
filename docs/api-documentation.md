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

## 8. Complete Administration Module (`/admin`)

All `/admin/*` endpoints strictly enforce `require_admin` dependency. Requests without a valid token return `401 Unauthorized`; requests from non-administrator roles return `403 Forbidden`. Administrative mutations automatically record timestamped entries in the `audit_logs` table.

- `GET /admin/dashboard` — Overview statistics (`total_users`, `total_satellites`, `total_simulations`, `active_sessions`, `network_events`).
- `GET /admin/users?limit=25&offset=0&q=search&role=admin|user` — Paginated list of registered users with roles, account status (`is_active`), and activity metrics.
- `GET /admin/users/{user_id}` — Detailed profile of a user including registered devices and recent simulations.
- `PUT /admin/users/{user_id}` — Updates role (`admin` / `user`), active status (`is_active`), or name. Self-demotion and self-deactivation are strictly forbidden.
- `GET /admin/satellites?limit=50&offset=0&status_filter=active|decommissioned` — Constellation management listing.
- `POST /admin/satellites` — Registers a new satellite record with Keplerian elements ($a, e, i, \Omega, \nu$) and status.
- `PUT /admin/satellites/{satellite_id}` — Updates orbital elements, designation, or operational status.
- `PATCH /admin/satellites/{satellite_id}/status?status=active|decommissioned` — Toggles active constellation state.
- `GET /admin/ground-stations` — Lists all gateway stations with coordinates.
- `POST /admin/ground-stations` — Creates a new ground gateway station.
- `PUT /admin/ground-stations/{station_id}` — Updates gateway station name, coordinates, or status.
- `DELETE /admin/ground-stations/{station_id}` — Permanently deletes a ground station record.
- `GET /admin/simulations?limit=25&offset=0&status_filter=visible|no_visibility|failed` — Constellation-wide simulation runs across all accounts.
- `GET /admin/sessions?limit=25&offset=0&status_filter=connected|ended` — Constellation-wide demo sessions with latest signal strength, latency, and packet loss.
- `POST /admin/sessions/{session_id}/terminate` — Authorized forced termination of any active connection session with audit recording.
- `GET /admin/events?limit=50&offset=0&event_type=...&q=...` — System-wide network event audit trail.
- `GET /admin/system-health` — Real-time server diagnostics: database engine status, connection pool health, table record counts, scientific simulation engine algorithms, and server uptime.
- `GET /admin/audit-logs?limit=50&offset=0&action=...&target_type=...` — Immutable audit log recording all administrative modifications.

---

## 9. System Health (`/health`)

- `GET /health` and `GET /api/v1/health` — Public endpoint returning `{ "status": "ok", "connectivity": "simulation_only" }`.

---

## 10. Mobile Network & Direct-to-Device Endpoints (`/network`)

The `/network/*` endpoints deliver mobile internet connectivity status detection, controlled synthetic speedtest streaming, benchmark recording, and aggregated Direct-to-Device (D2D) routing telemetry.

- `GET /network/ping`
  - Public endpoint measuring instantaneous server round-trip latency and validating active TCP connectivity.
  - Response (`200 OK`):
    ```json
    {
      "status": "online",
      "client_ip": "127.0.0.1",
      "server_time_utc": "2026-11-03T06:14:48.102900Z",
      "timestamp_ms": 1793686488102.9
    }
    ```
- `GET /network/speedtest/download?size_mb=2`
  - Streams controlled synthetic binary byte chunks (from 0.5 MB up to 10 MB) with `Content-Length` headers for accurate client download throughput calculation without disk I/O bottlenecks.
  - Response (`200 OK`): `StreamingResponse` (MIME: `application/octet-stream`).
- `POST /network/speedtest/upload`
  - Consumes incoming binary streaming payloads, computes duration and calculates upload throughput in Mbps.
  - Response (`200 OK`):
    ```json
    {
      "bytes_received": 524288,
      "duration_ms": 172.5,
      "upload_speed_mbps": 24.32,
      "timestamp": "2026-11-03T06:15:00.120Z"
    }
    ```
- `POST /network/tests`
  - Records a completed connectivity benchmark run into the database. Protected; links to authenticated user.
  - Body:
    ```json
    {
      "client_platform": "mobile_android",
      "ping_latency_ms": 28.5,
      "download_speed_mbps": 12.4,
      "upload_speed_mbps": 2.1,
      "packet_loss_percent": 0.0,
      "test_type": "internet_speedtest",
      "status": "completed",
      "server_location": "Bangalore Teleport Gateway"
    }
    ```
  - Response (`201 Created`): Full persisted `ConnectivityTestResponse` record with UUID and timestamp.
- `GET /network/tests?limit=25&offset=0`
  - Retrieves paginated history of past connectivity and throughput tests.
- `GET /network/d2d-dashboard?latitude_deg=float&longitude_deg=float`
  - Aggregated real-time Direct-to-Device simulation payload:
    - `mobile_device_status`: Platform, online status, IP address, battery %, and coordinates.
    - `internet_availability`: Cellular fallback vs 3GPP Rel-17 NTN active link mode.
    - `selected_satellite`: Active overhead LEO satellite with altitude, velocity, and ground subpoint.
    - `satellite_visibility`: Elevation angle, azimuth, slant distance, and Doppler shift ($\text{kHz}$).
    - `gateway_status`: Nearest operational Ka-band teleport station, feeder frequency, and distance.
    - `simulated_routing_path`: 5-step end-to-end hop diagram (`UE -> NTN Radio -> Satellite -> Feeder Gateway -> Internet UPF`).
    - `metrics`: RF signal level ($\text{dBm}$), $C/N_0$ ($\text{dB-Hz}$), latency, and throughput.
    - `prototype_disclaimer`: Simulation notice.

---

## 11. Satellite Gateways (`/gateways`)

Protected CRUD management for satellite teleport ground gateways operating high-capacity Ka-band feeder links.

- `GET /gateways?limit=25&offset=0&status_filter=operational`
  - Lists registered teleport stations with feeder frequencies, capacity (Gbps), coordinates, and supported satellites count.
- `GET /gateways/{id}`
  - Retrieves detailed parameters for a specific gateway.
- `POST /gateways`
  - Administrator/user registration of a teleport station:
    ```json
    {
      "name": "Bangalore Teleport Gateway",
      "latitude_deg": 13.0827,
      "longitude_deg": 77.5877,
      "elevation_m": 920.0,
      "feeder_frequency_ghz": 28.5,
      "status": "operational",
      "ip_address": "192.168.10.1",
      "uplink_capacity_gbps": 10.0,
      "downlink_capacity_gbps": 40.0,
      "satellite_ids": []
    }
    ```
- `PUT /gateways/{id}`
  - Updates gateway properties, capacities, feeder frequencies, or linked satellite IDs.
- `DELETE /gateways/{id}`
  - Permanently removes the gateway and disassociates its feeder links.
- `GET /gateways/{id}/links`
  - Lists all satellites currently associated with the specified gateway teleport.

