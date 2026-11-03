import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_temporary_database = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_temporary_database.name) / 'tests.db'}"
os.environ["SECRET_KEY"] = "tests-only-signing-key-not-for-deployment"
os.environ["TESTING"] = "1"

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
        owner_headers = register_and_login(client, "owner@example.com")
        other_headers = register_and_login(client, "other@example.com")

        # Satellite seeded
        sats = client.get("/api/v1/satellites", headers=owner_headers)
        assert sats.status_code == 200
        sat_list = sats.json()["items"]
        assert len(sat_list) >= 1
        satellite_id = sat_list[0]["id"]

        # Run simulation
        sim_res = client.post("/api/v1/simulations", headers=owner_headers, json={
            "latitude_deg": 12.9716, "longitude_deg": 77.5946
        })
        assert sim_res.status_code == 201
        sim_data = sim_res.json()
        assert sim_data["status"] in ("visible", "no_visibility")
        sim_id = sim_data["id"]

        # Connection session
        conn_res = client.post("/api/v1/connections", headers=owner_headers, json={
            "simulation_id": sim_id
        })
        assert conn_res.status_code == 201
        conn_id = conn_res.json()["id"]

        # Measurements
        m_res = client.get(f"/api/v1/measurements?session_id={conn_id}", headers=owner_headers)
        assert m_res.status_code == 200
        assert len(m_res.json()["items"]) >= 1

        # Events
        ev_res = client.get("/api/v1/events", headers=owner_headers)
        assert ev_res.status_code == 200
        assert len(ev_res.json()["items"]) >= 1

        # Isolation check: other user cannot see owner's connection
        other_conns = client.get("/api/v1/connections", headers=other_headers)
        assert other_conns.status_code == 200
        assert not any(c["id"] == conn_id for c in other_conns.json()["items"])


def test_admin_route_requires_admin_role() -> None:
    with TestClient(app) as client:
        headers = register_and_login(client, "regular@example.com")
        assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403


def test_ground_stations_listing() -> None:
    with TestClient(app) as client:
        headers = register_and_login(client, "station_user@example.com")
        stations = client.get("/api/v1/ground-stations", headers=headers)
        assert stations.status_code == 200
        assert "items" in stations.json()


def test_database_relationships() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert user is not None
        assert user.role.name == "user"
        assert len(user.simulations) >= 1
        assert len(user.connections) >= 1


def test_passes_telemetry_and_simulation_reports() -> None:
    with TestClient(app) as client:
        headers = register_and_login(client, "advanced_sim@example.com")

        # Passes
        passes = client.get("/api/v1/simulations/passes?latitude_deg=12.9716&longitude_deg=77.5946&duration_hours=6", headers=headers)
        assert passes.status_code == 200
        data = passes.json()
        assert "passes" in data

        # Telemetry
        sats = client.get("/api/v1/satellites", headers=headers).json()["items"]
        sat_id = sats[0]["id"]
        telem = client.get(f"/api/v1/satellites/{sat_id}/telemetry", headers=headers)
        assert telem.status_code == 200
        t_data = telem.json()
        assert "subsatellite_latitude_deg" in t_data
        assert "orbital_velocity_km_s" in t_data

        # Simulation Run & Report
        sim = client.post("/api/v1/simulations", headers=headers, json={"latitude_deg": 12.9716, "longitude_deg": 77.5946}).json()
        sim_id = sim["id"]
        report = client.get(f"/api/v1/simulations/{sim_id}/report", headers=headers)
        assert report.status_code == 200
        r_data = report.json()
        assert "rf_link_budget" in r_data
        assert "free_space_path_loss_db" in r_data["rf_link_budget"]

        # CSV Export
        csv_res = client.get(f"/api/v1/simulations/{sim_id}/export.csv", headers=headers)
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        assert "simulation_id" in csv_res.text


def register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={
        "name": "Test User", "email": email, "password": "a-very-safe-password"
    })
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "a-very-safe-password"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
