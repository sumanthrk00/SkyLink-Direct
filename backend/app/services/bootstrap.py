from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.models import GroundStation, Role, Satellite, SatelliteGateway, User


def initialize_reference_data(db: Session) -> None:
    for role_name in ("user", "admin"):
        if db.scalar(select(Role).where(Role.name == role_name)) is None:
            db.add(Role(name=role_name))
    db.flush()

    admin_role = db.scalar(select(Role).where(Role.name == "admin"))
    if admin_role and db.scalar(select(User).where(User.email == "admin@skylink.direct")) is None:
        db.add(User(
            name="Demo Administrator",
            email="admin@skylink.direct",
            password_hash=hash_password("AdminSecure2026!"),
            role=admin_role,
        ))

    satellites = (
        ("Demo LEO 01", 550.0, 53.0, 0.0, 0.0),
        ("Demo LEO 02", 550.0, 53.0, 120.0, 120.0),
        ("Demo LEO 03", 1200.0, 70.0, 240.0, 240.0),
        ("Demo LEO 04", 550.0, 53.0, 60.0, 45.0),
        ("Demo LEO 05", 550.0, 53.0, 180.0, 90.0),
        ("Demo LEO 06", 550.0, 53.0, 240.0, 135.0),
        ("Demo LEO 07", 550.0, 53.0, 300.0, 180.0),
        ("Demo LEO 08", 600.0, 45.0, 30.0, 225.0),
        ("Demo LEO 09", 600.0, 45.0, 90.0, 270.0),
        ("Demo LEO 10", 600.0, 45.0, 150.0, 315.0),
        ("Demo LEO 11", 600.0, 45.0, 210.0, 60.0),
        ("Demo LEO 12", 600.0, 45.0, 270.0, 150.0),
        ("Demo LEO 13", 550.0, 53.0, 330.0, 210.0),
        ("Demo LEO 14", 600.0, 53.0, 45.0, 280.0),
        ("Demo LEO 15", 600.0, 53.0, 105.0, 340.0),
        ("Demo LEO 16", 550.0, 53.0, 165.0, 40.0),
        ("Demo LEO 17", 550.0, 53.0, 225.0, 100.0),
        ("Demo LEO 18", 600.0, 53.0, 285.0, 160.0),
    )
    all_sats = []
    for name, altitude, inclination, raan, phase in satellites:
        sat = db.scalar(select(Satellite).where(Satellite.name == name))
        if sat is None:
            sat = Satellite(
                name=name,
                orbit_type="LEO",
                altitude_km=altitude,
                inclination_deg=inclination,
                raan_deg=raan,
                phase_deg=phase,
                status="active",
            )
            db.add(sat)
        all_sats.append(sat)
    db.flush()

    if db.scalar(select(GroundStation).where(GroundStation.name == "Demo Ground Station")) is None:
        db.add(GroundStation(name="Demo Ground Station", latitude_deg=12.9716, longitude_deg=77.5946))

    # Reference Satellite Gateways
    gateways_data = (
        ("Bangalore Teleport Gateway", 13.0827, 77.5877, 50.0, 28.5, "operational", "192.168.10.1", 10.0, 40.0),
        ("London Teleport Station", 51.5074, -0.1278, 25.0, 28.5, "operational", "192.168.20.1", 10.0, 40.0),
        ("California West Gateway", 37.7749, -122.4194, 15.0, 29.0, "operational", "192.168.30.1", 15.0, 50.0),
    )
    for name, lat, lon, elev, freq, status, ip, up_cap, down_cap in gateways_data:
        gw = db.scalar(select(SatelliteGateway).where(SatelliteGateway.name == name))
        if gw is None:
            gw = SatelliteGateway(
                name=name,
                latitude_deg=lat,
                longitude_deg=lon,
                elevation_m=elev,
                feeder_frequency_ghz=freq,
                status=status,
                ip_address=ip,
                uplink_capacity_gbps=up_cap,
                downlink_capacity_gbps=down_cap,
                satellites=all_sats[:6],
            )
            db.add(gw)

    db.commit()
