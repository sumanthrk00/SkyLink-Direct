from datetime import datetime, timezone
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import require_admin
from app.database import get_db
from app.models.models import (
    AuditLog,
    ConnectionSession,
    Device,
    GroundStation,
    NetworkEvent,
    Role,
    Satellite,
    SignalMeasurement,
    SimulationRun,
    User,
)
from app.schemas.schema import (
    AdminSessionItem,
    AdminSimulationItem,
    AdminSystemHealthResponse,
    AdminUserListItem,
    AdminUserUpdateRequest,
    AuditLogResponse,
    GroundStationCreateRequest,
    GroundStationResponse,
    GroundStationUpdateAdminRequest,
    PageResponse,
    SatelliteCreateAdminRequest,
    SatelliteResponse,
    SatelliteUpdateAdminRequest,
)

SERVER_START_TIME = time.time()

router = APIRouter(prefix="/admin", tags=["administration"])


def record_audit(
    db: Session,
    admin: User,
    action: str,
    target_type: str,
    target_id: str | None,
    details: str,
) -> AuditLog:
    entry = AuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(entry)
    db.add(NetworkEvent(
        user_id=admin.id,
        event_type=f"admin.{action}",
        description=f"Admin {admin.email}: {details}",
    ))
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# 1. System Overview Dashboard (Preserved)
# ---------------------------------------------------------------------------
@router.get("/dashboard")
def dashboard(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "total_users": int(db.scalar(select(func.count()).select_from(User)) or 0),
        "total_satellites": int(db.scalar(select(func.count()).select_from(Satellite)) or 0),
        "total_simulations": int(db.scalar(select(func.count()).select_from(SimulationRun)) or 0),
        "active_sessions": int(db.scalar(select(func.count()).select_from(ConnectionSession).where(
            ConnectionSession.status == "connected"
        )) or 0),
        "network_events": int(db.scalar(select(func.count()).select_from(NetworkEvent)) or 0),
    }


# ---------------------------------------------------------------------------
# 2. User Management
# ---------------------------------------------------------------------------
@router.get("/users", response_model=PageResponse)
def list_users(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    role: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(User).order_by(User.created_at.desc())
    if q:
        query_pattern = f"%{q.strip().lower()}%"
        statement = statement.where(or_(
            func.lower(User.name).like(query_pattern),
            func.lower(User.email).like(query_pattern),
        ))
    if role:
        statement = statement.join(Role).where(Role.name == role)

    base_count = count_for(User)
    if q:
        base_count = select(func.count()).select_from(User).where(or_(
            func.lower(User.name).like(f"%{q.strip().lower()}%"),
            func.lower(User.email).like(f"%{q.strip().lower()}%"),
        ))

    result = paginated(db, statement, base_count, limit, offset)
    items = []
    for u in result["items"]:
        sim_count = int(db.scalar(select(func.count()).select_from(SimulationRun).where(SimulationRun.user_id == u.id)) or 0)
        conn_count = int(db.scalar(select(func.count()).select_from(ConnectionSession).where(ConnectionSession.user_id == u.id)) or 0)
        items.append({
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "role": u.role.name if u.role else "user",
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "simulations_count": sim_count,
            "connections_count": conn_count,
        })
    result["items"] = items
    return result


@router.get("/users/{user_id}")
def get_user_detail(
    user_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sim_count = int(db.scalar(select(func.count()).select_from(SimulationRun).where(SimulationRun.user_id == user.id)) or 0)
    conn_count = int(db.scalar(select(func.count()).select_from(ConnectionSession).where(ConnectionSession.user_id == user.id)) or 0)
    devices = [
        {"id": str(d.id), "name": d.name, "platform": d.platform, "created_at": d.created_at.isoformat()}
        for d in db.scalars(select(Device).where(Device.user_id == user.id)).all()
    ]
    recent_sims = [
        {
            "id": str(s.id),
            "status": s.status,
            "latitude_deg": s.latitude_deg,
            "longitude_deg": s.longitude_deg,
            "elevation_deg": s.elevation_deg,
            "created_at": s.created_at.isoformat(),
        }
        for s in db.scalars(select(SimulationRun).where(SimulationRun.user_id == user.id).order_by(SimulationRun.created_at.desc()).limit(5)).all()
    ]

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role.name if user.role else "user",
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "simulations_count": sim_count,
        "connections_count": conn_count,
        "devices": devices,
        "recent_simulations": recent_sims,
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    changes = []
    if payload.name is not None and payload.name.strip():
        old_name = target.name
        target.name = payload.name.strip()
        changes.append(f"name: '{old_name}' -> '{target.name}'")

    if payload.role is not None:
        if payload.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'")
        if target.id == current_admin.id and payload.role != "admin":
            raise HTTPException(status_code=400, detail="Administrators cannot demote themselves")
        role_obj = db.scalar(select(Role).where(Role.name == payload.role))
        if role_obj and target.role_id != role_obj.id:
            old_role = target.role.name if target.role else "unknown"
            target.role_id = role_obj.id
            changes.append(f"role: '{old_role}' -> '{payload.role}'")

    if payload.is_active is not None:
        if target.id == current_admin.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="Administrators cannot deactivate themselves")
        if target.is_active != payload.is_active:
            target.is_active = payload.is_active
            changes.append(f"is_active: {target.is_active}")

    if changes:
        db.commit()
        db.refresh(target)
        record_audit(
            db=db,
            admin=current_admin,
            action="user.update",
            target_type="user",
            target_id=str(target.id),
            details=f"Updated user {target.email}: {', '.join(changes)}",
        )

    return {
        "id": str(target.id),
        "name": target.name,
        "email": target.email,
        "role": target.role.name if target.role else "user",
        "is_active": target.is_active,
        "created_at": target.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# 3. Satellite Management
# ---------------------------------------------------------------------------
@router.get("/satellites", response_model=PageResponse)
def list_admin_satellites(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(Satellite).order_by(Satellite.name.asc())
    if status_filter:
        statement = statement.where(Satellite.status == status_filter)

    count_stmt = count_for(Satellite)
    if status_filter:
        count_stmt = select(func.count()).select_from(Satellite).where(Satellite.status == status_filter)

    result = paginated(db, statement, count_stmt, limit, offset)
    result["items"] = [
        {
            "id": str(s.id),
            "name": s.name,
            "orbit_type": s.orbit_type,
            "altitude_km": s.altitude_km,
            "inclination_deg": s.inclination_deg,
            "raan_deg": s.raan_deg,
            "phase_deg": s.phase_deg,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in result["items"]
    ]
    return result


@router.post("/satellites", response_model=SatelliteResponse, status_code=status.HTTP_201_CREATED)
def create_satellite(
    payload: SatelliteCreateAdminRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Satellite:
    if db.scalar(select(Satellite).where(Satellite.name == payload.name.strip())) is not None:
        raise HTTPException(status_code=409, detail="A satellite with this name already exists")

    satellite = Satellite(
        name=payload.name.strip(),
        orbit_type=payload.orbit_type.strip(),
        altitude_km=payload.altitude_km,
        inclination_deg=payload.inclination_deg,
        raan_deg=payload.raan_deg,
        phase_deg=payload.phase_deg,
        status=payload.status.strip(),
    )
    db.add(satellite)
    db.commit()
    db.refresh(satellite)

    record_audit(
        db=db,
        admin=current_admin,
        action="satellite.create",
        target_type="satellite",
        target_id=str(satellite.id),
        details=f"Created satellite '{satellite.name}' (altitude: {satellite.altitude_km} km, inc: {satellite.inclination_deg}°)",
    )
    return satellite


@router.put("/satellites/{satellite_id}", response_model=SatelliteResponse)
def update_satellite(
    satellite_id: UUID,
    payload: SatelliteUpdateAdminRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Satellite:
    satellite = db.get(Satellite, satellite_id)
    if not satellite:
        raise HTTPException(status_code=404, detail="Satellite not found")

    changes = []
    if payload.name is not None and payload.name.strip():
        existing = db.scalar(select(Satellite).where(Satellite.name == payload.name.strip(), Satellite.id != satellite_id))
        if existing:
            raise HTTPException(status_code=409, detail="Satellite name already in use")
        changes.append(f"name: '{satellite.name}' -> '{payload.name.strip()}'")
        satellite.name = payload.name.strip()

    if payload.altitude_km is not None:
        changes.append(f"altitude_km: {satellite.altitude_km} -> {payload.altitude_km}")
        satellite.altitude_km = payload.altitude_km
    if payload.inclination_deg is not None:
        changes.append(f"inclination_deg: {satellite.inclination_deg} -> {payload.inclination_deg}")
        satellite.inclination_deg = payload.inclination_deg
    if payload.raan_deg is not None:
        changes.append(f"raan_deg: {satellite.raan_deg} -> {payload.raan_deg}")
        satellite.raan_deg = payload.raan_deg
    if payload.phase_deg is not None:
        changes.append(f"phase_deg: {satellite.phase_deg} -> {payload.phase_deg}")
        satellite.phase_deg = payload.phase_deg
    if payload.status is not None:
        changes.append(f"status: '{satellite.status}' -> '{payload.status.strip()}'")
        satellite.status = payload.status.strip()

    db.commit()
    db.refresh(satellite)

    if changes:
        record_audit(
            db=db,
            admin=current_admin,
            action="satellite.update",
            target_type="satellite",
            target_id=str(satellite.id),
            details=f"Updated satellite '{satellite.name}': {', '.join(changes)}",
        )

    return satellite


@router.patch("/satellites/{satellite_id}/status")
def toggle_satellite_status(
    satellite_id: UUID,
    status_val: str = Query(..., alias="status"),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    satellite = db.get(Satellite, satellite_id)
    if not satellite:
        raise HTTPException(status_code=404, detail="Satellite not found")

    old_status = satellite.status
    satellite.status = status_val.strip()
    db.commit()
    db.refresh(satellite)

    record_audit(
        db=db,
        admin=current_admin,
        action="satellite.status_change",
        target_type="satellite",
        target_id=str(satellite.id),
        details=f"Changed satellite '{satellite.name}' status from '{old_status}' to '{satellite.status}'",
    )
    return {"id": str(satellite.id), "name": satellite.name, "status": satellite.status}


# ---------------------------------------------------------------------------
# 4. Ground Station Management
# ---------------------------------------------------------------------------
@router.get("/ground-stations", response_model=PageResponse)
def list_admin_ground_stations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(GroundStation).order_by(GroundStation.name.asc())
    result = paginated(db, statement, count_for(GroundStation), limit, offset)
    result["items"] = [
        GroundStationResponse.model_validate(item).model_dump(mode="json")
        for item in result["items"]
    ]
    return result


@router.post("/ground-stations", response_model=GroundStationResponse, status_code=status.HTTP_201_CREATED)
def create_admin_ground_station(
    payload: GroundStationCreateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GroundStationResponse:
    if db.scalar(select(GroundStation).where(GroundStation.name == payload.name.strip())) is not None:
        raise HTTPException(status_code=409, detail="A ground station with this name already exists")

    station = GroundStation(
        name=payload.name.strip(),
        latitude_deg=payload.latitude_deg,
        longitude_deg=payload.longitude_deg,
        status=payload.status.strip(),
    )
    db.add(station)
    db.commit()
    db.refresh(station)

    record_audit(
        db=db,
        admin=current_admin,
        action="ground_station.create",
        target_type="ground_station",
        target_id=str(station.id),
        details=f"Created ground station '{station.name}' at ({station.latitude_deg}°, {station.longitude_deg}°)",
    )
    return GroundStationResponse.model_validate(station)


@router.put("/ground-stations/{station_id}", response_model=GroundStationResponse)
def update_ground_station(
    station_id: UUID,
    payload: GroundStationUpdateAdminRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GroundStationResponse:
    station = db.get(GroundStation, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Ground station not found")

    changes = []
    if payload.name is not None and payload.name.strip():
        existing = db.scalar(select(GroundStation).where(GroundStation.name == payload.name.strip(), GroundStation.id != station_id))
        if existing:
            raise HTTPException(status_code=409, detail="Ground station name already in use")
        changes.append(f"name: '{station.name}' -> '{payload.name.strip()}'")
        station.name = payload.name.strip()

    if payload.latitude_deg is not None:
        changes.append(f"latitude_deg: {station.latitude_deg} -> {payload.latitude_deg}")
        station.latitude_deg = payload.latitude_deg
    if payload.longitude_deg is not None:
        changes.append(f"longitude_deg: {station.longitude_deg} -> {payload.longitude_deg}")
        station.longitude_deg = payload.longitude_deg
    if payload.status is not None:
        changes.append(f"status: '{station.status}' -> '{payload.status.strip()}'")
        station.status = payload.status.strip()

    db.commit()
    db.refresh(station)

    if changes:
        record_audit(
            db=db,
            admin=current_admin,
            action="ground_station.update",
            target_type="ground_station",
            target_id=str(station.id),
            details=f"Updated ground station '{station.name}': {', '.join(changes)}",
        )

    return GroundStationResponse.model_validate(station)


@router.delete("/ground-stations/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ground_station(
    station_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    station = db.get(GroundStation, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Ground station not found")

    name = station.name
    db.delete(station)
    db.commit()

    record_audit(
        db=db,
        admin=current_admin,
        action="ground_station.delete",
        target_type="ground_station",
        target_id=str(station_id),
        details=f"Deleted ground station '{name}'",
    )


# ---------------------------------------------------------------------------
# 5. Simulation Management
# ---------------------------------------------------------------------------
@router.get("/simulations", response_model=PageResponse)
def list_admin_simulations(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = (
        select(SimulationRun)
        .order_by(SimulationRun.created_at.desc())
    )
    if status_filter:
        statement = statement.where(SimulationRun.status == status_filter)

    count_stmt = count_for(SimulationRun)
    if status_filter:
        count_stmt = select(func.count()).select_from(SimulationRun).where(SimulationRun.status == status_filter)

    result = paginated(db, statement, count_stmt, limit, offset)
    items = []
    for s in result["items"]:
        user = db.get(User, s.user_id)
        sat = db.get(Satellite, s.satellite_id) if s.satellite_id else None
        items.append({
            "id": str(s.id),
            "user_id": str(s.user_id),
            "user_email": user.email if user else "Unknown",
            "satellite_name": sat.name if sat else None,
            "status": s.status,
            "latitude_deg": s.latitude_deg,
            "longitude_deg": s.longitude_deg,
            "elevation_deg": s.elevation_deg,
            "distance_km": s.distance_km,
            "signal_strength": s.signal_strength,
            "latency_ms": s.latency_ms,
            "packet_loss": s.packet_loss,
            "download_mbps": s.download_mbps,
            "upload_mbps": s.upload_mbps,
            "created_at": s.created_at.isoformat(),
        })
    result["items"] = items
    return result


# ---------------------------------------------------------------------------
# 6. Session Management & Authorized Termination
# ---------------------------------------------------------------------------
@router.get("/sessions", response_model=PageResponse)
def list_admin_sessions(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(ConnectionSession).order_by(ConnectionSession.started_at.desc())
    if status_filter:
        statement = statement.where(ConnectionSession.status == status_filter)

    count_stmt = count_for(ConnectionSession)
    if status_filter:
        count_stmt = select(func.count()).select_from(ConnectionSession).where(ConnectionSession.status == status_filter)

    result = paginated(db, statement, count_stmt, limit, offset)
    items = []
    for s in result["items"]:
        user = db.get(User, s.user_id)
        sat = db.get(Satellite, s.satellite_id) if s.satellite_id else None
        last_m = db.scalars(
            select(SignalMeasurement)
            .where(SignalMeasurement.session_id == s.id)
            .order_by(SignalMeasurement.measured_at.desc())
            .limit(1)
        ).first()

        items.append({
            "id": str(s.id),
            "user_id": str(s.user_id),
            "user_email": user.email if user else "Unknown",
            "satellite_name": sat.name if sat else None,
            "status": s.status,
            "started_at": s.started_at.isoformat(),
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "signal_strength": last_m.signal_strength if last_m else None,
            "latency_ms": last_m.latency_ms if last_m else None,
            "packet_loss": last_m.packet_loss if last_m else None,
        })
    result["items"] = items
    return result


@router.post("/sessions/{session_id}/terminate")
def admin_terminate_session(
    session_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(ConnectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Connection session not found")

    if session.status != "connected":
        return {
            "id": str(session.id),
            "status": session.status,
            "message": "Session was already ended",
        }

    session.status = "ended"
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    record_audit(
        db=db,
        admin=current_admin,
        action="session.terminate",
        target_type="session",
        target_id=str(session.id),
        details=f"Terminated demo session {session.id} for user {session.user_id}",
    )

    return {
        "id": str(session.id),
        "status": session.status,
        "ended_at": session.ended_at.isoformat(),
        "message": "Session terminated successfully by administrator",
    }


# ---------------------------------------------------------------------------
# 7. Network Event Management & Filtering
# ---------------------------------------------------------------------------
@router.get("/events", response_model=PageResponse)
def list_admin_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(NetworkEvent).order_by(NetworkEvent.created_at.desc())
    if event_type:
        statement = statement.where(NetworkEvent.event_type == event_type)
    if q:
        statement = statement.where(func.lower(NetworkEvent.description).like(f"%{q.strip().lower()}%"))

    count_stmt = count_for(NetworkEvent)
    if event_type or q:
        count_stmt = select(func.count()).select_from(NetworkEvent)
        if event_type:
            count_stmt = count_stmt.where(NetworkEvent.event_type == event_type)
        if q:
            count_stmt = count_stmt.where(func.lower(NetworkEvent.description).like(f"%{q.strip().lower()}%"))

    result = paginated(db, statement, count_stmt, limit, offset)
    result["items"] = [
        {
            "id": str(e.id),
            "user_id": str(e.user_id) if e.user_id else None,
            "event_type": e.event_type,
            "description": e.description,
            "created_at": e.created_at.isoformat(),
        }
        for e in result["items"]
    ]
    return result


# ---------------------------------------------------------------------------
# 8. System Monitoring & Diagnostics
# ---------------------------------------------------------------------------
@router.get("/system-health", response_model=AdminSystemHealthResponse)
def get_system_health(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSystemHealthResponse:
    counts = {
        "users": int(db.scalar(select(func.count()).select_from(User)) or 0),
        "satellites": int(db.scalar(select(func.count()).select_from(Satellite)) or 0),
        "ground_stations": int(db.scalar(select(func.count()).select_from(GroundStation)) or 0),
        "simulation_runs": int(db.scalar(select(func.count()).select_from(SimulationRun)) or 0),
        "connection_sessions": int(db.scalar(select(func.count()).select_from(ConnectionSession)) or 0),
        "signal_measurements": int(db.scalar(select(func.count()).select_from(SignalMeasurement)) or 0),
        "network_events": int(db.scalar(select(func.count()).select_from(NetworkEvent)) or 0),
        "audit_logs": int(db.scalar(select(func.count()).select_from(AuditLog)) or 0),
    }

    uptime = time.time() - SERVER_START_TIME

    return AdminSystemHealthResponse(
        api_status="healthy",
        connectivity_mode="simulation_only",
        database_engine="SQLite (SQLAlchemy Engine, WAL mode)",
        database_connected=True,
        table_counts=counts,
        simulation_engine={
            "mechanics": "Keplerian 2-body with J2 secular earth oblateness perturbation",
            "coordinates": "WGS-84 reference ellipsoid with Bowring geodetic conversion",
            "rf_propagation": "Friis Free Space Path Loss (FSPL) with ITU-R P.676 absorption",
            "refraction": "Saastamoinen tropospheric apparent elevation angle correction",
            "cellular_standard": "3GPP Release 17 NTN link budget MCS adaptation",
        },
        system_uptime_seconds=round(uptime, 2),
        server_time_utc=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 9. Audit Logs
# ---------------------------------------------------------------------------
@router.get("/audit-logs", response_model=PageResponse)
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        statement = statement.where(AuditLog.action == action)
    if target_type:
        statement = statement.where(AuditLog.target_type == target_type)

    count_stmt = count_for(AuditLog)
    if action or target_type:
        count_stmt = select(func.count()).select_from(AuditLog)
        if action:
            count_stmt = count_stmt.where(AuditLog.action == action)
        if target_type:
            count_stmt = count_stmt.where(AuditLog.target_type == target_type)

    result = paginated(db, statement, count_stmt, limit, offset)
    result["items"] = [
        {
            "id": str(log.id),
            "admin_id": str(log.admin_id) if log.admin_id else None,
            "admin_email": log.admin_email,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in result["items"]
    ]
    return result
