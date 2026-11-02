from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import NetworkEvent, Satellite, SimulationRun, User
from app.schemas.schema import PageResponse, SimulationRequest, SimulationResponse
from app.simulator.engine import estimate_link

router = APIRouter(prefix="/simulations", tags=["simulations"])


def response_for(run: SimulationRun) -> SimulationResponse:
    return SimulationResponse(
        id=run.id, status=run.status, latitude_deg=run.latitude_deg, longitude_deg=run.longitude_deg,
        satellite_id=run.satellite_id, satellite_name=run.satellite.name if run.satellite else None,
        elevation_deg=run.elevation_deg, distance_km=run.distance_km, signal_strength=run.signal_strength,
        latency_ms=run.latency_ms, packet_loss=run.packet_loss, download_mbps=run.download_mbps,
        upload_mbps=run.upload_mbps, created_at=run.created_at,
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
