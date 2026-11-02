from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import GroundStation, Role, Satellite


def initialize_reference_data(db: Session) -> None:
    for role_name in ("user", "admin"):
        if db.scalar(select(Role).where(Role.name == role_name)) is None:
            db.add(Role(name=role_name))
    satellites = (
        ("Demo LEO 01", 550.0, 53.0, 0.0, 0.0),
        ("Demo LEO 02", 550.0, 53.0, 120.0, 120.0),
        ("Demo LEO 03", 1200.0, 70.0, 240.0, 240.0),
    )
    for name, altitude, inclination, raan, phase in satellites:
        if db.scalar(select(Satellite).where(Satellite.name == name)) is None:
            db.add(Satellite(
                name=name,
                orbit_type="LEO",
                altitude_km=altitude,
                inclination_deg=inclination,
                raan_deg=raan,
                phase_deg=phase,
                status="active",
            ))
    if db.scalar(select(GroundStation).where(GroundStation.name == "Demo Ground Station")) is None:
        db.add(GroundStation(name="Demo Ground Station", latitude_deg=12.9716, longitude_deg=77.5946))
    db.commit()
