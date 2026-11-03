import os
import tempfile
from pathlib import Path
from uuid import uuid4

_temporary_database = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_temporary_database.name) / 'admin_tests.db'}"
os.environ["SECRET_KEY"] = "admin-tests-signing-key-not-for-deployment"
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import Role, Satellite, User, GroundStation, SimulationRun, ConnectionSession
from app.core.security import hash_password


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin_role = Role(name="admin")
        user_role = Role(name="user")
        db.add_all([admin_role, user_role])
        db.flush()

        admin_user = User(
            name="Super Admin",
            email="superadmin@skylink.direct",
            password_hash=hash_password("SuperAdmin2026!"),
            role_id=admin_role.id,
        )
        normal_user = User(
            name="Regular Joe",
            email="joe@skylink.direct",
            password_hash=hash_password("RegularJoe2026!"),
            role_id=user_role.id,
        )
        db.add_all([admin_user, normal_user])
        db.commit()


def teardown_module() -> None:
    engine.dispose()


def test_admin_permissions_enforced() -> None:
    with TestClient(app) as client:
        # Unauthenticated request fails with 401
        assert client.get("/api/v1/admin/dashboard").status_code == 401
        assert client.get("/api/v1/admin/users").status_code == 401
        assert client.get("/api/v1/admin/system-health").status_code == 401

        # Regular user login
        joe_login = client.post("/api/v1/auth/login", json={
            "email": "joe@skylink.direct", "password": "RegularJoe2026!"
        })
        assert joe_login.status_code == 200
        joe_token = joe_login.json()["access_token"]
        joe_headers = {"Authorization": f"Bearer {joe_token}"}

        # Regular user accessing admin endpoints gets 403 Forbidden
        assert client.get("/api/v1/admin/dashboard", headers=joe_headers).status_code == 403
        assert client.get("/api/v1/admin/users", headers=joe_headers).status_code == 403
        assert client.get("/api/v1/admin/satellites", headers=joe_headers).status_code == 403
        assert client.get("/api/v1/admin/system-health", headers=joe_headers).status_code == 403
        assert client.get("/api/v1/admin/audit-logs", headers=joe_headers).status_code == 403


def test_admin_user_management_and_audit() -> None:
    with TestClient(app) as client:
        # Admin login
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "superadmin@skylink.direct", "password": "SuperAdmin2026!"
        })
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # List users
        users_res = client.get("/api/v1/admin/users", headers=admin_headers)
        assert users_res.status_code == 200
        users_data = users_res.json()
        assert users_data["total"] >= 2

        # Find Joe's ID
        joe_entry = next(u for u in users_data["items"] if u["email"] == "joe@skylink.direct")
        joe_id = joe_entry["id"]

        # View Joe's detail
        detail_res = client.get(f"/api/v1/admin/users/{joe_id}", headers=admin_headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["name"] == "Regular Joe"

        # Update Joe: toggle status and promote to admin
        update_res = client.put(f"/api/v1/admin/users/{joe_id}", headers=admin_headers, json={
            "name": "Joe Promoted",
            "role": "admin",
            "is_active": True,
        })
        assert update_res.status_code == 200
        assert update_res.json()["role"] == "admin"
        assert update_res.json()["name"] == "Joe Promoted"

        # Demote Joe back
        demote_res = client.put(f"/api/v1/admin/users/{joe_id}", headers=admin_headers, json={
            "role": "user",
        })
        assert demote_res.status_code == 200
        assert demote_res.json()["role"] == "user"

        # Verify admin cannot deactivate or demote self
        my_profile = client.get("/api/v1/users/me", headers=admin_headers).json()
        self_id = my_profile["id"]
        assert client.put(f"/api/v1/admin/users/{self_id}", headers=admin_headers, json={
            "is_active": False
        }).status_code == 400
        assert client.put(f"/api/v1/admin/users/{self_id}", headers=admin_headers, json={
            "role": "user"
        }).status_code == 400


def test_admin_satellite_management() -> None:
    with TestClient(app) as client:
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "superadmin@skylink.direct", "password": "SuperAdmin2026!"
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Create new satellite
        sat_create = client.post("/api/v1/admin/satellites", headers=admin_headers, json={
            "name": "Admin Test Sat 99",
            "orbit_type": "LEO",
            "altitude_km": 620.0,
            "inclination_deg": 51.6,
            "raan_deg": 45.0,
            "phase_deg": 90.0,
            "status": "active",
        })
        assert sat_create.status_code == 201
        sat_id = sat_create.json()["id"]

        # Duplicate satellite name fails
        assert client.post("/api/v1/admin/satellites", headers=admin_headers, json={
            "name": "Admin Test Sat 99",
            "altitude_km": 600.0,
            "inclination_deg": 50.0,
        }).status_code == 409

        # Edit satellite
        sat_update = client.put(f"/api/v1/admin/satellites/{sat_id}", headers=admin_headers, json={
            "altitude_km": 650.0,
            "status": "testing",
        })
        assert sat_update.status_code == 200
        assert sat_update.json()["altitude_km"] == 650.0

        # Toggle status to decommissioned
        sat_toggle = client.patch(f"/api/v1/admin/satellites/{sat_id}/status?status=decommissioned", headers=admin_headers)
        assert sat_toggle.status_code == 200
        assert sat_toggle.json()["status"] == "decommissioned"

        # List satellites
        sat_list = client.get("/api/v1/admin/satellites", headers=admin_headers)
        assert sat_list.status_code == 200
        assert any(s["id"] == sat_id for s in sat_list.json()["items"])


def test_admin_ground_station_management() -> None:
    with TestClient(app) as client:
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "superadmin@skylink.direct", "password": "SuperAdmin2026!"
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Add ground station
        station_create = client.post("/api/v1/admin/ground-stations", headers=admin_headers, json={
            "name": "Admin Test Station",
            "latitude_deg": 28.6139,
            "longitude_deg": 77.2090,
            "status": "operational",
        })
        assert station_create.status_code == 201
        station_id = station_create.json()["id"]

        # Edit ground station
        station_update = client.put(f"/api/v1/admin/ground-stations/{station_id}", headers=admin_headers, json={
            "name": "Admin Test Station Renamed",
            "latitude_deg": 28.7000,
            "status": "maintenance",
        })
        assert station_update.status_code == 200
        assert station_update.json()["name"] == "Admin Test Station Renamed"
        assert station_update.json()["status"] == "maintenance"

        # Delete ground station
        del_res = client.delete(f"/api/v1/admin/ground-stations/{station_id}", headers=admin_headers)
        assert del_res.status_code == 204


def test_admin_session_management_and_termination() -> None:
    with TestClient(app) as client:
        # Joe creates a session
        joe_login = client.post("/api/v1/auth/login", json={
            "email": "joe@skylink.direct", "password": "RegularJoe2026!"
        })
        joe_headers = {"Authorization": f"Bearer {joe_login.json()['access_token']}"}
        conn_res = client.post("/api/v1/connections", headers=joe_headers, json={
            "latitude_deg": 12.9716, "longitude_deg": 77.5946
        })
        assert conn_res.status_code == 201
        session_id = conn_res.json()["id"]

        # Admin logs in
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "superadmin@skylink.direct", "password": "SuperAdmin2026!"
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Admin lists all sessions
        sessions_res = client.get("/api/v1/admin/sessions", headers=admin_headers)
        assert sessions_res.status_code == 200
        assert any(s["id"] == session_id for s in sessions_res.json()["items"])

        # Admin force terminates Joe's session
        term_res = client.post(f"/api/v1/admin/sessions/{session_id}/terminate", headers=admin_headers)
        assert term_res.status_code == 200
        assert term_res.json()["status"] == "ended"


def test_admin_system_monitoring_and_audit_logs() -> None:
    with TestClient(app) as client:
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "superadmin@skylink.direct", "password": "SuperAdmin2026!"
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # System health
        health_res = client.get("/api/v1/admin/system-health", headers=admin_headers)
        assert health_res.status_code == 200
        health = health_res.json()
        assert health["api_status"] == "healthy"
        assert health["database_connected"] is True
        assert "users" in health["table_counts"]
        assert health["table_counts"]["users"] >= 2
        assert "simulation_engine" in health

        # Audit logs check
        logs_res = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
        assert logs_res.status_code == 200
        logs = logs_res.json()
        assert logs["total"] >= 1
        actions = [log["action"] for log in logs["items"]]
        assert "user.update" in actions or "satellite.create" in actions or "session.terminate" in actions
