import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import NetworkEvent, Satellite, SimulationRun, User
from app.schemas.schema import (
    PageResponse,
    PassPredictionItem,
    PassPredictionResponse,
    SimulationReportResponse,
    SimulationRequest,
    SimulationResponse,
)
from app.simulator.engine import estimate_link, predict_passes, satellite_subpoint
from app.simulator.rf import compute_link_budget

router = APIRouter(prefix="/simulations", tags=["simulations"])


def response_for(run: SimulationRun) -> SimulationResponse:
    return SimulationResponse(
        id=run.id,
        status=run.status,
        latitude_deg=run.latitude_deg,
        longitude_deg=run.longitude_deg,
        satellite_id=run.satellite_id,
        satellite_name=run.satellite.name if run.satellite else None,
        elevation_deg=run.elevation_deg,
        distance_km=run.distance_km,
        signal_strength=run.signal_strength,
        latency_ms=run.latency_ms,
        packet_loss=run.packet_loss,
        download_mbps=run.download_mbps,
        upload_mbps=run.upload_mbps,
        created_at=run.created_at,
    )


@router.post("", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def create_simulation(
    payload: SimulationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationResponse:
    satellites = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
    estimate = estimate_link(satellites, payload.latitude_deg, payload.longitude_deg)
    run = SimulationRun(
        user_id=user.id,
        satellite_id=estimate.satellite.id if estimate.satellite else None,
        status="visible" if estimate.visible else "no_visibility",
        latitude_deg=payload.latitude_deg,
        longitude_deg=payload.longitude_deg,
        elevation_deg=estimate.elevation_deg,
        distance_km=estimate.distance_km,
        signal_strength=estimate.signal_strength,
        latency_ms=estimate.latency_ms,
        packet_loss=estimate.packet_loss,
        download_mbps=estimate.download_mbps,
        upload_mbps=estimate.upload_mbps,
    )
    db.add(run)
    db.add(NetworkEvent(user_id=user.id, event_type="simulation.created", description=f"Simulation {run.id} created"))
    db.commit()
    db.refresh(run)
    return response_for(run)


@router.get("/passes", response_model=PassPredictionResponse)
def get_pass_predictions(
    latitude_deg: float = Query(ge=-90.0, le=90.0),
    longitude_deg: float = Query(ge=-180.0, le=180.0),
    duration_hours: float = Query(default=12.0, ge=1.0, le=48.0),
    min_elevation_deg: float = Query(default=10.0, ge=0.0, le=80.0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PassPredictionResponse:
    satellites = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
    now = datetime.now(timezone.utc)
    passes = predict_passes(
        satellites=satellites,
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        start_time=now,
        duration_hours=duration_hours,
        min_elevation_deg=min_elevation_deg,
    )

    items = [
        PassPredictionItem(
            satellite_id=p.satellite_id,
            satellite_name=p.satellite_name,
            aos_utc=p.aos_utc,
            tca_utc=p.tca_utc,
            los_utc=p.los_utc,
            max_elevation_deg=p.max_elevation_deg,
            duration_seconds=p.duration_seconds,
            tca_distance_km=p.tca_distance_km,
            tca_azimuth_deg=p.tca_azimuth_deg,
        )
        for p in passes
    ]

    return PassPredictionResponse(
        observer_latitude_deg=latitude_deg,
        observer_longitude_deg=longitude_deg,
        start_utc=now,
        duration_hours=duration_hours,
        min_elevation_deg=min_elevation_deg,
        total_passes=len(items),
        passes=items,
    )


@router.get("/find-visible")
def find_visible_location(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    satellites = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
    if not satellites:
        raise HTTPException(status_code=404, detail="No active satellites found")
    now = datetime.now(timezone.utc)
    sat = satellites[0]
    lat, lon, alt = satellite_subpoint(sat, now)
    return {
        "latitude_deg": lat,
        "longitude_deg": lon,
        "satellite_name": sat.name,
        "altitude_km": alt,
    }


@router.get("", response_model=PageResponse)
def list_simulations(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(SimulationRun).where(SimulationRun.user_id == user.id).order_by(SimulationRun.created_at.desc())
    count = count_for(SimulationRun).where(SimulationRun.user_id == user.id)
    result = paginated(db, statement, count, limit, offset)
    result["items"] = [response_for(item).model_dump(mode="json") for item in result["items"]]
    return result


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(
    simulation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SimulationResponse:
    run = db.scalar(select(SimulationRun).where(SimulationRun.id == simulation_id, SimulationRun.user_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return response_for(run)


@router.get("/{simulation_id}/report", response_model=SimulationReportResponse)
def get_simulation_report(
    simulation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationReportResponse:
    run = db.scalar(select(SimulationRun).where(SimulationRun.id == simulation_id, SimulationRun.user_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    rf = compute_link_budget(
        distance_km=run.distance_km,
        elevation_deg=run.elevation_deg,
    )

    sat_info = None
    if run.satellite:
        sat_info = {
            "id": str(run.satellite.id),
            "name": run.satellite.name,
            "orbit_type": run.satellite.orbit_type,
            "altitude_km": run.satellite.altitude_km,
            "inclination_deg": run.satellite.inclination_deg,
            "raan_deg": run.satellite.raan_deg,
        }

    return SimulationReportResponse(
        simulation_id=run.id,
        created_at=run.created_at,
        observer_location={"latitude_deg": run.latitude_deg, "longitude_deg": run.longitude_deg},
        satellite=sat_info,
        rf_link_budget={
            "free_space_path_loss_db": rf.fspl_db,
            "atmospheric_absorption_db": rf.atmospheric_loss_db,
            "total_path_loss_db": rf.total_path_loss_db,
            "carrier_frequency_mhz": rf.carrier_freq_mhz,
            "c_n0_db_hz": rf.c_n0_db_hz,
            "snr_db": rf.snr_db,
            "apparent_elevation_deg": rf.apparent_elevation_deg,
            "rx_power_dbm": rf.received_power_dbm,
        },
        throughput_capacity={
            "download_mbps": run.download_mbps,
            "upload_mbps": run.upload_mbps,
            "latency_ms": run.latency_ms,
            "packet_loss_percent": run.packet_loss,
        },
        channel_status="optimal" if run.elevation_deg >= 25.0 else ("adequate" if run.elevation_deg > 0 else "blocked"),
        prototype_disclaimer="Calculated using standard 3GPP TR 38.811 NTN model and WGS-84 coordinate frame. Illustrative simulation only; not live RF service.",
    )


@router.get("/{simulation_id}/export.csv")
def export_simulation_csv(
    simulation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    run = db.scalar(select(SimulationRun).where(SimulationRun.id == simulation_id, SimulationRun.user_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "simulation_id", "created_at", "status", "observer_lat", "observer_lon",
        "satellite_name", "elevation_deg", "distance_km", "signal_dbm",
        "latency_ms", "packet_loss_pct", "download_mbps", "upload_mbps"
    ])
    writer.writerow([
        str(run.id), run.created_at.isoformat(), run.status, run.latitude_deg, run.longitude_deg,
        run.satellite.name if run.satellite else "", run.elevation_deg, run.distance_km, run.signal_strength,
        run.latency_ms, run.packet_loss, run.download_mbps, run.upload_mbps
    ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=simulation_{simulation_id}.csv"},
    )
