from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import ConnectionSession, NetworkEvent, Satellite, SignalMeasurement, SimulationRun, User
from app.schemas.schema import ConnectionCreateRequest, ConnectionResponse, PageResponse
from app.simulator.engine import estimate_link

router = APIRouter(prefix="/connections", tags=["connections"])


def response_for(session: ConnectionSession) -> ConnectionResponse:
    return ConnectionResponse(
        id=session.id, satellite_id=session.satellite_id,
        satellite_name=session.satellite.name if session.satellite else None,
        status=session.status, started_at=session.started_at, ended_at=session.ended_at,
    )


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    # End any previously active session for this user so a new demo session starts smoothly
    active_sessions = db.scalars(select(ConnectionSession).where(
        ConnectionSession.user_id == user.id, ConnectionSession.status == "connected"
    )).all()
    for active in active_sessions:
        active.status = "ended"
        active.ended_at = datetime.now(timezone.utc)

    satellite_id = None
    measurement = (-110.0, 28.0, 1.0)

    if payload.simulation_id is not None:
        run = db.scalar(select(SimulationRun).where(
            SimulationRun.id == payload.simulation_id, SimulationRun.user_id == user.id
        ))
        if run is None:
            raise HTTPException(status_code=404, detail="Simulation not found")
        if run.status == "visible" and run.satellite_id:
            satellite_id = run.satellite_id
            measurement = (run.signal_strength, run.latency_ms, run.packet_loss)
        else:
            # Fall back to calculating current link for the simulation location
            satellites = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
            estimate = estimate_link(satellites, run.latitude_deg, run.longitude_deg)
            if estimate.satellite:
                satellite_id = estimate.satellite.id
                measurement = (
                    estimate.signal_strength,
                    estimate.latency_ms if estimate.latency_ms > 0 else 28.0,
                    estimate.packet_loss if estimate.packet_loss < 100 else 1.2,
                )
    else:
        satellites = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
        lat = payload.latitude_deg if payload.latitude_deg is not None else 12.9716
        lon = payload.longitude_deg if payload.longitude_deg is not None else 77.5946
        estimate = estimate_link(satellites, lat, lon)
        if estimate.satellite:
            satellite_id = estimate.satellite.id
            measurement = (
                estimate.signal_strength,
                estimate.latency_ms if estimate.latency_ms > 0 else 28.0,
                estimate.packet_loss if estimate.packet_loss < 100 else 1.2,
            )

    if satellite_id is None:
        first_sat = db.scalar(select(Satellite).where(Satellite.status == "active"))
        if first_sat is not None:
            satellite_id = first_sat.id

    if satellite_id is None:
        raise HTTPException(status_code=409, detail="No demo satellite is currently available")

    session = ConnectionSession(user_id=user.id, satellite_id=satellite_id, status="connected")
    db.add(session)
    db.flush()
    db.add(SignalMeasurement(
        session_id=session.id,
        signal_strength=measurement[0],
        latency_ms=measurement[1],
        packet_loss=measurement[2],
    ))
    db.add(NetworkEvent(user_id=user.id, event_type="connection.started", description="Demo connection started"))
    db.commit()
    db.refresh(session)
    return response_for(session)


@router.get("", response_model=PageResponse)
def list_connections(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(ConnectionSession).where(ConnectionSession.user_id == user.id).order_by(ConnectionSession.started_at.desc())
    result = paginated(db, statement, count_for(ConnectionSession).where(ConnectionSession.user_id == user.id), limit, offset)
    result["items"] = [response_for(item).model_dump(mode="json") for item in result["items"]]
    return result


@router.post("/{connection_id}/end", response_model=ConnectionResponse)
def end_connection(
    connection_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    session = db.scalar(select(ConnectionSession).where(
        ConnectionSession.id == connection_id, ConnectionSession.user_id == user.id
    ))
    if session is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if session.status == "connected":
        session.status = "ended"
        session.ended_at = datetime.now(timezone.utc)
        db.add(NetworkEvent(user_id=user.id, event_type="connection.ended", description="Demo connection ended"))
        db.commit()
        db.refresh(session)
    return response_for(session)
