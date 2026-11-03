import os
import tempfile
from pathlib import Path

_temporary_database = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_temporary_database.name) / 'phase1_tests.db'}"
os.environ["SECRET_KEY"] = "phase1-tests-signing-key-not-for-deployment"
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import Role, Satellite, SatelliteGateway, User
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
        mobile_user = User(
            name="Mobile Tester",
            email="mobile@skylink.direct",
            password_hash=hash_password("MobileSecure2026!"),
            role_id=user_role.id,
        )
        db.add_all([admin_user, mobile_user])
        db.flush()

        # Seed satellites
        sat1 = Satellite(name="LEO-Test-01", orbit_type="LEO", altitude_km=550.0, inclination_deg=53.0, status="active")
        sat2 = Satellite(name="LEO-Test-02", orbit_type="LEO", altitude_km=600.0, inclination_deg=53.0, status="active")
        db.add_all([sat1, sat2])
        db.flush()

        # Seed gateway
        gw = SatelliteGateway(
            name="Test Gateway Alpha",
            latitude_deg=13.0,
            longitude_deg=77.6,
            elevation_m=50.0,
            feeder_frequency_ghz=28.5,
            status="operational",
            satellites=[sat1, sat2],
        )
        db.add(gw)
        db.commit()


def teardown_module() -> None:
    engine.dispose()


def test_network_ping_and_connectivity() -> None:
    with TestClient(app) as client:
        res = client.get("/api/v1/network/ping")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert "client_ip" in data
        assert "timestamp_ms" in data


def test_speedtest_download_streaming() -> None:
    with TestClient(app) as client:
        size = 65536 * 2  # 128 KB
        res = client.get(f"/api/v1/network/speedtest/download?size_bytes={size}")
        assert res.status_code == 200
        assert res.headers["content-length"] == str(size)
        assert len(res.content) == size


def test_speedtest_upload_and_metrics() -> None:
    with TestClient(app) as client:
        payload = b"X" * (1024 * 64)  # 64 KB
        res = client.post("/api/v1/network/speedtest/upload", content=payload, headers={"Content-Type": "application/octet-stream"})
        assert res.status_code == 200
        data = res.json()
        assert data["bytes_received"] == len(payload)
        assert data["upload_speed_mbps"] > 0
        assert data["duration_ms"] > 0


def test_connectivity_test_recording_and_history() -> None:
    with TestClient(app) as client:
        # Login mobile user
        login_res = client.post("/api/v1/auth/login", json={"email": "mobile@skylink.direct", "password": "MobileSecure2026!"})
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Record test
        test_rec = client.post("/api/v1/network/tests", headers=headers, json={
            "client_platform": "mobile_android",
            "ping_latency_ms": 28.5,
            "download_speed_mbps": 12.4,
            "upload_speed_mbps": 3.8,
            "packet_loss_percent": 0.5,
            "test_type": "internet_speedtest",
            "status": "completed",
            "server_location": "Bangalore Gateway",
        })
        assert test_rec.status_code == 201
        test_id = test_rec.json()["id"]

        # List history
        history_res = client.get("/api/v1/network/tests", headers=headers)
        assert history_res.status_code == 200
        items = history_res.json()["items"]
        assert len(items) >= 1
        assert items[0]["id"] == test_id


def test_gateway_crud_and_feeder_links() -> None:
    with TestClient(app) as client:
        # Admin login
        admin_login = client.post("/api/v1/auth/login", json={"email": "superadmin@skylink.direct", "password": "SuperAdmin2026!"})
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # 1. List gateways
        list_res = client.get("/api/v1/gateways", headers=admin_headers)
        assert list_res.status_code == 200
        assert list_res.json()["total"] >= 1
        target_gw = next(item for item in list_res.json()["items"] if item["name"] == "Test Gateway Alpha")
        gw_id = target_gw["id"]

        # 2. Get gateway detail
        gw_res = client.get(f"/api/v1/gateways/{gw_id}", headers=admin_headers)
        assert gw_res.status_code == 200
        assert gw_res.json()["name"] == "Test Gateway Alpha"
        assert len(gw_res.json()["supported_satellites"]) >= 1

        # 3. Create new gateway
        create_res = client.post("/api/v1/gateways", headers=admin_headers, json={
            "name": "New Regional Gateway",
            "latitude_deg": 28.6,
            "longitude_deg": 77.2,
            "elevation_m": 210.0,
            "feeder_frequency_ghz": 29.5,
            "status": "operational",
            "ip_address": "10.0.1.1",
            "uplink_capacity_gbps": 20.0,
            "downlink_capacity_gbps": 80.0,
        })
        assert create_res.status_code == 201
        new_gw_id = create_res.json()["id"]

        # 4. Update gateway
        update_res = client.put(f"/api/v1/gateways/{new_gw_id}", headers=admin_headers, json={
            "status": "maintenance"
        })
        assert update_res.status_code == 200
        assert update_res.json()["status"] == "maintenance"

        # 5. Check Feeder links
        links_res = client.get(f"/api/v1/gateways/{gw_id}/links", headers=admin_headers)
        assert links_res.status_code == 200
        assert "active_feeder_links_count" in links_res.json()

        # 6. Delete created gateway
        del_res = client.delete(f"/api/v1/gateways/{new_gw_id}", headers=admin_headers)
        assert del_res.status_code == 204


def test_direct_to_device_dashboard_endpoint() -> None:
    with TestClient(app) as client:
        login_res = client.post("/api/v1/auth/login", json={"email": "mobile@skylink.direct", "password": "MobileSecure2026!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        d2d_res = client.get("/api/v1/network/d2d-dashboard?latitude_deg=12.9716&longitude_deg=77.5946&platform=mobile_android", headers=headers)
        assert d2d_res.status_code == 200
        data = d2d_res.json()
        assert "mobile_device_status" in data
        assert data["mobile_device_status"]["platform"] == "mobile_android"
        assert "internet_availability" in data
        assert "simulated_routing_path" in data
        assert len(data["simulated_routing_path"]) == 5
        assert "metrics" in data
        assert "prototype_disclaimer" in data
