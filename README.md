# SkyLink Direct

SkyLink Direct is a full-stack **satellite connectivity simulation prototype**. It models visibility against synthetic demonstration satellites and estimates link metrics. It does not connect to satellites, mobile networks, licensed spectrum, or the public internet.

## Implemented

- FastAPI REST API with JWT login/logout, Argon2 password hashing and password updates, user profiles, role checks, rate-limited authentication and paginated history.
- SQLAlchemy relational models for users, roles, devices, satellites, ground stations, simulations, sessions, measurements, network events and notifications.
- Simplified orbital geometry and clearly labelled illustrative signal, latency, packet loss and throughput estimates.
- React + TypeScript web dashboard for authentication, network overview, satellite inventory, simulation history, demo sessions, profile and administrator statistics.
- Flutter client source using the same API for authentication, dashboard, simulation, satellites, sessions and profile.
- SQLite for local Python development; PostgreSQL via Docker Compose.
- OpenAPI documentation at `/docs` when the API is running.

## Quick start: Windows with SQLite

Open PowerShell in the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
$env:DATABASE_URL = "sqlite:///./skylink.db"
$env:SECRET_KEY = "replace-with-a-long-random-development-secret"
$env:CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://192.168.31.141:5173"
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --reload --env-file .env
```

In a second PowerShell window:

```powershell
cd web
npm install
npm run dev
```

The local CORS list includes `http://192.168.31.141:5173` because the web page is opened through that LAN address. The web client calls the API at `http://localhost:8000`, which is correct when the browser and backend run on the same computer. If your computer's LAN IP changes, update its web origin in `.env` (`CORS_ORIGINS`). Restart both servers after changing configuration. Open `http://192.168.31.141:5173` (or `http://localhost:5173`), then register and sign in. API docs are at `http://localhost:8000/docs`; health is `http://localhost:8000/health`.

## Docker Compose: PostgreSQL, API and web

Copy `.env.example` to `.env`, replace the secrets, then run:

```powershell
docker compose up --build
```

The web client is at `http://localhost:5173`, API docs at `http://localhost:8000/docs`. Stop with `Ctrl+C`; `docker compose down` preserves the database volume. `docker compose down -v` removes it.

## Flutter mobile app

Install Flutter SDK. From `mobile`, generate Android/iOS platform wrappers if absent, fetch packages and run:

```powershell
cd mobile
flutter create --platforms android,ios .
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

`10.0.2.2` routes an Android emulator to the host. On a physical Android device use the development computer's LAN IP, such as `http://192.168.1.20:8000/api/v1`. For an iOS simulator use `http://localhost:8000/api/v1`. Override the compile-time `API_BASE_URL` for each environment. The app stores its token locally and uses the same API as web.

## Administrator account

Public registration assigns only the ordinary `user` role; there is no public administrator registration. Promote a trusted account in local development after registering it:

```powershell
python -c "import sys; sys.path.insert(0, 'backend'); from app.database import SessionLocal; from app.models.models import User, Role; from sqlalchemy import select; db=SessionLocal(); user=db.scalar(select(User).where(User.email=='admin@example.com')); role=db.scalar(select(Role).where(Role.name=='admin')); user.role=role; db.commit(); db.close()"
```

Replace the email with the account to promote. Administration then appears in the web navigation.

## Simulation assumptions and limitations

The simulator propagates circular demonstration orbits from synthetic altitude, inclination, RAAN and phase parameters. It uses spherical Earth geometry and Earth rotation. A fixed illustrative 2 GHz free-space path-loss approximation derives an uncalibrated signal value; latency has fixed overhead and throughput/loss are elevation heuristics. The model omits real spacecraft ephemerides, antenna patterns, transmit power, receiver sensitivity, atmospheric attenuation, spectrum allocation, interference, modem behavior, handovers and network backhaul. Geometric visibility does not imply a usable radio link.

Scientific orbital propagation would require validated current TLE/OMM inputs and a suitable library such as Skyfield. Real direct-to-device service requires compatible radio hardware, satellite/operator integration, spectrum authorization and RF/network validation. Those dependencies are outside this prototype.

## Repository layout

```text
backend/     FastAPI application, SQLAlchemy models, simulator and API tests
web/         React + TypeScript + Vite client
mobile/      Flutter client source
database/    SQL schema and demonstration seed reference
docs/        Architecture, ERD, API notes and test plan
```

## Configuration and security

Copy `.env.example` to `.env` and configure secrets and origins. `SECRET_KEY` must be a long random secret for any shared deployment. Restrict `CORS_ORIGINS` to served web origins. Compose's sample database password and the local development key are placeholders. Use HTTPS, managed secret storage, backups and monitoring before public deployment.

JWT logout revokes the current token until expiry. Authentication rate limiting is in-process and designed for a single-instance prototype; multiple workers need a shared rate limiter. An initial Alembic schema revision is included; local startup also creates missing tables for convenience. Apply later reviewed revisions with `alembic upgrade head` from `backend`.

## API quick reference

All routes use `/api/v1`. Except registration/login, calls require `Authorization: Bearer <access_token>`.

| Area | Routes |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout` |
| User | `GET /users/me`, `PUT /users/me`, `PUT /users/me/password` |
| Satellites | `GET /satellites`, `GET /satellites/{id}` |
| Simulations | `POST /simulations`, `GET /simulations`, `GET /simulations/{id}` |
| Connections | `POST /connections`, `GET /connections`, `POST /connections/{id}/end` |
| Measurements/events | `GET /measurements`, `GET /events` |
| Administration | `GET /admin/dashboard` (administrator only) |

List endpoints accept `limit` and `offset`. The running `/docs` page includes request/response schemas.

## Verification

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend\tests -q
cd web
npm install
npm run build
npm test
```

Flutter verification (with Flutter installed): `cd mobile; flutter analyze; flutter test`.
