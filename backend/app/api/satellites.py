import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import Satellite, User
from app.schemas.schema import PageResponse, SatelliteResponse, SatelliteTelemetryResponse
from app.simulator.engine import satellite_position_ecef, satellite_subpoint, satellite_to_elements

router = APIRouter(prefix="/satellites", tags=["satellites"])


@router.get("", response_model=PageResponse)
def list_satellites(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(Satellite).order_by(Satellite.name)
    result = paginated(db, statement, count_for(Satellite), limit, offset)
    result["items"] = [SatelliteResponse.model_validate(item).model_dump(mode="json") for item in result["items"]]
    return result


@router.get("/{satellite_id}", response_model=SatelliteResponse)
def get_satellite(satellite_id: UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Satellite:
    satellite = db.get(Satellite, satellite_id)
    if satellite is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return satellite


@router.get("/{satellite_id}/telemetry", response_model=SatelliteTelemetryResponse)
def get_satellite_telemetry(
    satellite_id: UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SatelliteTelemetryResponse:
    satellite = db.get(Satellite, satellite_id)
    if satellite is None:
        raise HTTPException(status_code=404, detail="Satellite not found")

    now = datetime.now(timezone.utc)
    r_ecef, v_ecef = satellite_position_ecef(satellite, now)
    sub_lat, sub_lon, sub_alt = satellite_subpoint(satellite, now)
    elements = satellite_to_elements(satellite)

    velocity_km_s = math.sqrt(v_ecef[0] ** 2 + v_ecef[1] ** 2 + v_ecef[2] ** 2)
    period_min = elements.orbital_period_s / 60.0

    return SatelliteTelemetryResponse(
        satellite_id=satellite.id,
        name=satellite.name,
        orbit_type=satellite.orbit_type,
        altitude_km=satellite.altitude_km,
        timestamp_utc=now,
        subsatellite_latitude_deg=sub_lat,
        subsatellite_longitude_deg=sub_lon,
        orbital_velocity_km_s=round(velocity_km_s, 3),
        orbital_period_minutes=round(period_min, 2),
        ecef_coordinates_km={
            "x": round(r_ecef[0], 2),
            "y": round(r_ecef[1], 2),
            "z": round(r_ecef[2], 2),
        },
    )
