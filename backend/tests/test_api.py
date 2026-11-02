import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_temporary_database = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_temporary_database.name) / 'tests.db'}"
os.environ["SECRET_KEY"] = "tests-only-signing-key-not-for-deployment"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import Role, Satellite, User
from app.core.security import hash_password
from app.simulator.engine import estimate_link


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module() -> None:
    engine.dispose()


def test_registration_login_profile_and_logout() -> None:
    with TestClient(app) as client:
        registration = client.post("/api/v1/auth/register", json={
            "name": "Demo User", "email": "demo@example.com", "password": "a-very-safe-password"
        })
        assert registration.status_code == 201
        assert "password_hash" not in registration.json()

        assert client.post("/api/v1/auth/register", json={
            "name": "Duplicate", "email": "demo@example.com", "password": "a-very-safe-password"
        }).status_code == 409
        assert client.post("/api/v1/auth/login", json={
            "email": "demo@example.com", "password": "incorrect-password"
        }).status_code == 401

        login = client.post("/api/v1/auth/login", json={
            "email": "demo@example.com", "password": "a-very-safe-password"
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert client.get("/api/v1/users/me").status_code == 401
        profile = client.get("/api/v1/users/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["email"] == "demo@example.com"
        updated = client.put("/api/v1/users/me", headers=headers, json={"name": "Renamed"})
        assert updated.json()["name"] == "Renamed"
        assert client.put("/api/v1/users/me/password", headers=headers, json={
            "current_password": "wrong-current-password", "new_password": "another-safe-password"
        }).status_code == 400
        assert client.put("/api/v1/users/me/password", headers=headers, json={
            "current_password": "a-very-safe-password", "new_password": "another-safe-password"
        }).status_code == 204
        assert client.post("/api/v1/auth/login", json={
            "email": "demo@example.com", "password": "a-very-safe-password"
        }).status_code == 401
        assert client.post("/api/v1/auth/login", json={
            "email": "demo@example.com", "password": "another-safe-password"
        }).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/users/me", headers=headers).status_code == 401


def test_satellite_simulation_connection_and_ownership() -> None:
    with TestClient(app) as client:
        register_and_login(client, "owner@example.com")
        owner_headers = client.headers
        satellites = client.get("/api/v1/satellites", headers=owner_headers)
        assert satellites.status_code == 200
        assert satellites.json()["total"] >= 3
        assert satellites.json()["items"][0]["altitude_km"] > 0

        latitude, longitude = find_visible_location()
        simulation = client.post("/api/v1/simulations", headers=owner_headers, json={
            "latitude_deg": latitude, "longitude_deg": longitude
        })
        assert simulation.status_code == 201
        result = simulation.json()
        assert result["status"] == "visible"
        assert result["result_type"] == "illustrative_estimate"
        assert result["latency_ms"] > 0
        assert client.get(f"/api/v1/simulations/{result['id']}", headers=owner_headers).status_code == 200

        connection = client.post("/api/v1/connections", headers=owner_headers, json={
            "simulation_id": result["id"]
        })
        assert connection.status_code == 201
        connection_id = connection.json()["id"]
        measurements = client.get("/api/v1/measurements", headers=owner_headers)
        assert measurements.status_code == 200
        assert measurements.json()["total"] == 1
        ended = client.post(f"/api/v1/connections/{connection_id}/end", headers=owner_headers)
        assert ended.status_code == 200
        assert ended.json()["status"] == "ended"

        register_and_login(client, "other@example.com")
        other_headers = client.headers
        assert client.get(f"/api/v1/simulations/{result['id']}", headers=other_headers).status_code == 404
        assert client.post(f"/api/v1/connections/{connection_id}/end", headers=other_headers).status_code == 404


def test_admin_route_requires_admin_role() -> None:
    with TestClient(app) as client:
        headers = register_and_login(client, "regular@example.com")
        assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403


def test_database_relationships() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert user is not None
        assert user.role.name == "user"
        assert len(user.simulations) >= 1


def register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={
        "name": "Test User", "email": email, "password": "a-very-safe-password"
    })
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "a-very-safe-password"
    })
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    client.headers.update(headers)
    return headers


def find_visible_location() -> tuple[float, float]:
    with SessionLocal() as db:
        satellites = list(db.scalars(select(Satellite)).all())
        now = datetime.now(timezone.utc)
        for latitude in range(-80, 81, 10):
            for longitude in range(-180, 180, 10):
                result = estimate_link(satellites, latitude, longitude, now)
                if result.visible:
                    return float(latitude), float(longitude)
    raise AssertionError("Seeded demo satellites should be visible from at least one test location")
