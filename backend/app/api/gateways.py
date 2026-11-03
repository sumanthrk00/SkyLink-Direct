import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.models import (
    AuditLog,
    NetworkEvent,
    Satellite,
    SatelliteGateway,
    User,
)
from app.schemas.schema import (
    GatewayCreateRequest,
    GatewayResponse,
    GatewayUpdateRequest,
    PageResponse,
)
from app.simulator.engine import estimate_link, satellite_position_ecef
from app.simulator.rf import free_space_path_loss_db

router = APIRouter(prefix="/gateways", tags=["gateways"])


def gateway_to_response(gw: SatelliteGateway) -> GatewayResponse:
    sat_names = [s.name for s in gw.satellites]
    return GatewayResponse(
        id=gw.id,
        name=gw.name,
        latitude_deg=gw.latitude_deg,
        longitude_deg=gw.longitude_deg,
        elevation_m=gw.elevation_m,
        feeder_frequency_ghz=gw.feeder_frequency_ghz,
        status=gw.status,
        ip_address=gw.ip_address,
        uplink_capacity_gbps=gw.uplink_capacity_gbps,
        downlink_capacity_gbps=gw.downlink_capacity_gbps,
        supported_satellites_count=len(gw.satellites),
        supported_satellites=sat_names,
        created_at=gw.created_at,
    )


# ---------------------------------------------------------------------------
# 1. List Gateways
# ---------------------------------------------------------------------------
@router.get("", response_model=PageResponse)
def list_gateways(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(SatelliteGateway).order_by(SatelliteGateway.name.asc())
    result = paginated(db, statement, count_for(SatelliteGateway), limit, offset)
    result["items"] = [
        gateway_to_response(gw).model_dump(mode="json")
        for gw in result["items"]
    ]
    return result


# ---------------------------------------------------------------------------
# 2. Get Single Gateway
# ---------------------------------------------------------------------------
@router.get("/{gateway_id}", response_model=GatewayResponse)
def get_gateway(
    gateway_id: UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GatewayResponse:
    gw = db.get(SatelliteGateway, gateway_id)
    if not gw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found")
    return gateway_to_response(gw)


# ---------------------------------------------------------------------------
# 3. Create Gateway
# ---------------------------------------------------------------------------
@router.post("", response_model=GatewayResponse, status_code=status.HTTP_201_CREATED)
def create_gateway(
    payload: GatewayCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GatewayResponse:
    if db.scalar(select(SatelliteGateway).where(SatelliteGateway.name == payload.name.strip())) is not None:
        raise HTTPException(status_code=409, detail="A gateway with this name already exists")

    sats = []
    if payload.satellite_ids:
        sats = list(db.scalars(select(Satellite).where(Satellite.id.in_(payload.satellite_ids))).all())
    else:
        # Link first active satellites by default
        sats = list(db.scalars(select(Satellite).where(Satellite.status == "active").limit(6)).all())

    gw = SatelliteGateway(
        name=payload.name.strip(),
        latitude_deg=payload.latitude_deg,
        longitude_deg=payload.longitude_deg,
        elevation_m=payload.elevation_m,
        feeder_frequency_ghz=payload.feeder_frequency_ghz,
        status=payload.status.strip(),
        ip_address=payload.ip_address.strip(),
        uplink_capacity_gbps=payload.uplink_capacity_gbps,
        downlink_capacity_gbps=payload.downlink_capacity_gbps,
        satellites=sats,
    )
    db.add(gw)
    db.add(AuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action="gateway.create",
        target_type="gateway",
        details=f"Created satellite gateway '{gw.name}' at ({gw.latitude_deg}°, {gw.longitude_deg}°)",
    ))
    db.add(NetworkEvent(
        user_id=admin.id,
        event_type="gateway.created",
        description=f"Satellite gateway '{gw.name}' registered with {len(sats)} linked satellites",
    ))
    db.commit()
    db.refresh(gw)
    return gateway_to_response(gw)


# ---------------------------------------------------------------------------
# 4. Update Gateway
# ---------------------------------------------------------------------------
@router.put("/{gateway_id}", response_model=GatewayResponse)
def update_gateway(
    gateway_id: UUID,
    payload: GatewayUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GatewayResponse:
    gw = db.get(SatelliteGateway, gateway_id)
    if not gw:
        raise HTTPException(status_code=404, detail="Gateway not found")

    changes = []
    if payload.name is not None and payload.name.strip():
        existing = db.scalar(select(SatelliteGateway).where(SatelliteGateway.name == payload.name.strip(), SatelliteGateway.id != gateway_id))
        if existing:
            raise HTTPException(status_code=409, detail="Gateway name already in use")
        changes.append(f"name: '{gw.name}' -> '{payload.name.strip()}'")
        gw.name = payload.name.strip()

    if payload.latitude_deg is not None:
        gw.latitude_deg = payload.latitude_deg
        changes.append(f"lat: {gw.latitude_deg}")
    if payload.longitude_deg is not None:
        gw.longitude_deg = payload.longitude_deg
        changes.append(f"lon: {gw.longitude_deg}")
    if payload.elevation_m is not None:
        gw.elevation_m = payload.elevation_m
    if payload.feeder_frequency_ghz is not None:
        gw.feeder_frequency_ghz = payload.feeder_frequency_ghz
    if payload.status is not None:
        gw.status = payload.status.strip()
        changes.append(f"status: '{gw.status}'")
    if payload.ip_address is not None:
        gw.ip_address = payload.ip_address.strip()
    if payload.uplink_capacity_gbps is not None:
        gw.uplink_capacity_gbps = payload.uplink_capacity_gbps
    if payload.downlink_capacity_gbps is not None:
        gw.downlink_capacity_gbps = payload.downlink_capacity_gbps

    if payload.satellite_ids is not None:
        sats = list(db.scalars(select(Satellite).where(Satellite.id.in_(payload.satellite_ids))).all())
        gw.satellites = sats
        changes.append(f"linked_satellites: {len(sats)}")

    db.add(AuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action="gateway.update",
        target_type="gateway",
        target_id=str(gw.id),
        details=f"Updated gateway '{gw.name}': {', '.join(changes)}",
    ))
    db.commit()
    db.refresh(gw)
    return gateway_to_response(gw)


# ---------------------------------------------------------------------------
# 5. Delete Gateway
# ---------------------------------------------------------------------------
@router.delete("/{gateway_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gateway(
    gateway_id: UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    gw = db.get(SatelliteGateway, gateway_id)
    if not gw:
        raise HTTPException(status_code=404, detail="Gateway not found")

    name = gw.name
    db.delete(gw)
    db.add(AuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action="gateway.delete",
        target_type="gateway",
        target_id=str(gateway_id),
        details=f"Deleted gateway '{name}'",
    ))
    db.commit()


# ---------------------------------------------------------------------------
# 6. Gateway Monitoring & Active Feeder Links
# ---------------------------------------------------------------------------
@router.get("/{gateway_id}/links")
def get_gateway_feeder_links(
    gateway_id: UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    gw = db.get(SatelliteGateway, gateway_id)
    if not gw:
        raise HTTPException(status_code=404, detail="Gateway not found")

    now = datetime.now(timezone.utc)
    sats = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
    feeder_links = []

    for s in sats:
        estimate = estimate_link([s], gw.latitude_deg, gw.longitude_deg, now)
        # Feeder links use higher elevation mask (typically 5° or 10°)
        if estimate.elevation_deg >= 5.0:
            # Ka-band FSPL
            ka_fspl = free_space_path_loss_db(estimate.distance_km, gw.feeder_frequency_ghz * 1000.0)
            feeder_links.append({
                "satellite_id": str(s.id),
                "satellite_name": s.name,
                "elevation_deg": round(estimate.elevation_deg, 2),
                "azimuth_deg": round(estimate.azimuth_deg, 1),
                "slant_range_km": round(estimate.distance_km, 1),
                "carrier_frequency_ghz": gw.feeder_frequency_ghz,
                "feeder_fspl_db": round(ka_fspl, 1),
                "link_quality": "excellent" if estimate.elevation_deg >= 25.0 else "nominal" if estimate.elevation_deg >= 10.0 else "low_horizon",
                "uplink_margin_db": round(max(20.0 - (ka_fspl - 170.0), 3.0), 1),
            })

    return {
        "gateway_id": str(gw.id),
        "gateway_name": gw.name,
        "coordinates": {"latitude_deg": gw.latitude_deg, "longitude_deg": gw.longitude_deg},
        "feeder_frequency_ghz": gw.feeder_frequency_ghz,
        "status": gw.status,
        "active_feeder_links_count": len(feeder_links),
        "feeder_links": feeder_links,
        "timestamp_utc": now.isoformat(),
    }

