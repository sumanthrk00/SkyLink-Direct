import io
import math
import os
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import (
    ConnectivityTest,
    NetworkEvent,
    Satellite,
    SatelliteGateway,
    User,
)
from app.schemas.schema import (
    ConnectivityTestCreateRequest,
    ConnectivityTestResponse,
    DirectToDeviceDashboardResponse,
    PageResponse,
    PingResponse,
    UploadTestResponse,
)
from app.simulator.engine import estimate_link, satellite_position_ecef, satellite_subpoint
from app.simulator.rf import calculate_doppler_shift, free_space_path_loss_db

router = APIRouter(prefix="/network", tags=["network"])


# ---------------------------------------------------------------------------
# 1. Connectivity & Latency Ping
# ---------------------------------------------------------------------------
@router.get("/ping", response_model=PingResponse)
def ping(request: Request) -> PingResponse:
    now = datetime.now(timezone.utc)
    client_host = request.client.host if request.client else "127.0.0.1"
    return PingResponse(
        status="online",
        client_ip=client_host,
        server_time_utc=now,
        timestamp_ms=time.time() * 1000.0,
    )


# ---------------------------------------------------------------------------
# 2. Controlled Download Speed Test
# ---------------------------------------------------------------------------
@router.get("/speedtest/download")
def speedtest_download(
    size_bytes: int = Query(default=1048576, ge=1024, le=10485760),  # 1 KB to 10 MB (default 1 MB)
) -> StreamingResponse:
    """Streams controlled synthetic byte chunks for accurate client-side download speed calculation."""
    chunk_size = 65536  # 64 KB per chunk
    block = b"\x00" * chunk_size

    def byte_generator():
        remaining = size_bytes
        while remaining > 0:
            current = min(remaining, chunk_size)
            yield block[:current]
            remaining -= current

    return StreamingResponse(
        byte_generator(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(size_bytes),
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-SpeedTest-Bytes": str(size_bytes),
        },
    )


# ---------------------------------------------------------------------------
# 3. Controlled Upload Speed Test
# ---------------------------------------------------------------------------
@router.post("/speedtest/upload", response_model=UploadTestResponse)
async def speedtest_upload(request: Request) -> UploadTestResponse:
    """Consumes uploaded byte payload and returns duration and measured throughput in Mbps."""
    start_time = time.perf_counter()
    total_bytes = 0

    async for chunk in request.stream():
        total_bytes += len(chunk)

    elapsed_s = max(time.perf_counter() - start_time, 0.0001)
    duration_ms = elapsed_s * 1000.0
    upload_speed_mbps = (total_bytes * 8.0) / (elapsed_s * 1_000_000.0)

    return UploadTestResponse(
        bytes_received=total_bytes,
        duration_ms=round(duration_ms, 2),
        upload_speed_mbps=round(upload_speed_mbps, 2),
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 4. Connectivity Test Records & History
# ---------------------------------------------------------------------------
@router.post("/tests", response_model=ConnectivityTestResponse, status_code=status.HTTP_201_CREATED)
def record_connectivity_test(
    payload: ConnectivityTestCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectivityTest:
    test = ConnectivityTest(
        user_id=user.id,
        client_platform=payload.client_platform,
        ping_latency_ms=payload.ping_latency_ms,
        download_speed_mbps=payload.download_speed_mbps,
        upload_speed_mbps=payload.upload_speed_mbps,
        packet_loss_percent=payload.packet_loss_percent,
        test_type=payload.test_type,
        status=payload.status,
        server_location=payload.server_location,
    )
    db.add(test)
    db.add(NetworkEvent(
        user_id=user.id,
        event_type="network.speedtest",
        description=f"Speedtest ({payload.client_platform}): {payload.download_speed_mbps:.1f} Mbps down / {payload.upload_speed_mbps:.1f} Mbps up, {payload.ping_latency_ms:.1f} ms ping",
    ))
    db.commit()
    db.refresh(test)
    return test


@router.get("/tests", response_model=PageResponse)
def list_connectivity_tests(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = (
        select(ConnectivityTest)
        .where(ConnectivityTest.user_id == user.id)
        .order_by(ConnectivityTest.created_at.desc())
    )
    count_stmt = count_for(ConnectivityTest).where(ConnectivityTest.user_id == user.id)
    result = paginated(db, statement, count_stmt, limit, offset)
    result["items"] = [
        {
            "id": str(t.id),
            "client_platform": t.client_platform,
            "ping_latency_ms": t.ping_latency_ms,
            "download_speed_mbps": t.download_speed_mbps,
            "upload_speed_mbps": t.upload_speed_mbps,
            "packet_loss_percent": t.packet_loss_percent,
            "test_type": t.test_type,
            "status": t.status,
            "server_location": t.server_location,
            "created_at": t.created_at.isoformat(),
        }
        for t in result["items"]
    ]
    return result


# ---------------------------------------------------------------------------
# 5. Direct-to-Device (D2D) End-to-End Dashboard
# ---------------------------------------------------------------------------
@router.get("/d2d-dashboard", response_model=DirectToDeviceDashboardResponse)
def get_d2d_dashboard(
    latitude_deg: float = Query(default=12.9716, ge=-90.0, le=90.0),
    longitude_deg: float = Query(default=77.5946, ge=-180.0, le=180.0),
    platform: str = Query(default="mobile_android"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectToDeviceDashboardResponse:
    now = datetime.now(timezone.utc)

    # 1. Evaluate constellation visibility from user location
    active_sats = list(db.scalars(select(Satellite).where(Satellite.status == "active")).all())
    link_estimate = estimate_link(active_sats, latitude_deg, longitude_deg, now)

    sat_info = None
    sat_visibility = None
    if link_estimate.satellite:
        sub_lat, sub_lon, sub_alt = satellite_subpoint(link_estimate.satellite, now)
        r_ecef, v_ecef = satellite_position_ecef(link_estimate.satellite, now)
        vel_mag = math.sqrt(v_ecef[0] ** 2 + v_ecef[1] ** 2 + v_ecef[2] ** 2)

        sat_info = {
            "id": str(link_estimate.satellite.id),
            "name": link_estimate.satellite.name,
            "orbit_type": link_estimate.satellite.orbit_type,
            "altitude_km": link_estimate.satellite.altitude_km,
            "orbital_velocity_km_s": round(vel_mag, 2),
            "subsatellite_latitude": round(sub_lat, 4),
            "subsatellite_longitude": round(sub_lon, 4),
        }
        sat_visibility = {
            "status": "visible" if link_estimate.elevation_deg >= 10.0 else "marginal",
            "elevation_deg": round(link_estimate.elevation_deg, 2),
            "azimuth_deg": round(link_estimate.azimuth_deg, 1),
            "slant_range_km": round(link_estimate.distance_km, 1),
            "doppler_shift_khz": round(link_estimate.doppler_shift_hz / 1000.0, 2),
        }

    # 2. Select Nearest Satellite Gateway
    gateways = list(db.scalars(select(SatelliteGateway).where(SatelliteGateway.status == "operational")).all())
    best_gateway = None
    best_dist = float("inf")
    for gw in gateways:
        dlat = math.radians(gw.latitude_deg - latitude_deg)
        dlon = math.radians(gw.longitude_deg - longitude_deg)
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(math.radians(latitude_deg))
            * math.cos(math.radians(gw.latitude_deg))
            * math.sin(dlon / 2.0) ** 2
        )
        dist_km = 6371.0 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        if dist_km < best_dist:
            best_dist = dist_km
            best_gateway = gw

    gw_info = None
    if best_gateway:
        gw_info = {
            "id": str(best_gateway.id),
            "name": best_gateway.name,
            "latitude_deg": best_gateway.latitude_deg,
            "longitude_deg": best_gateway.longitude_deg,
            "status": best_gateway.status,
            "feeder_frequency_ghz": best_gateway.feeder_frequency_ghz,
            "egress_ip": best_gateway.ip_address,
            "distance_from_user_km": round(best_dist, 1),
        }

    # 3. Simulated End-to-End Routing Path
    is_sat_visible = link_estimate.elevation_deg >= 10.0
    routing_path = [
        {
            "step": 1,
            "node": "Mobile User Equipment (UE)",
            "role": "Direct-to-Device Transceiver",
            "protocol": "3GPP Rel-17 NTN User Equipment",
            "status": "active",
            "details": f"Platform: {platform} at ({latitude_deg:.2f}°, {longitude_deg:.2f}°)",
        },
        {
            "step": 2,
            "node": "Satellite Radio Access Link",
            "role": "Service Link (S-Band 2.0 GHz)",
            "protocol": "NR-NTN Orthogonal Frequency Division Multiplexing",
            "status": "connected" if is_sat_visible else "degraded",
            "details": f"Elevation: {link_estimate.elevation_deg:.1f}° · Signal: {link_estimate.signal_strength:.1f} dBm",
        },
        {
            "step": 3,
            "node": f"Satellite Node: {link_estimate.satellite.name if link_estimate.satellite else 'Constellation'}",
            "role": "LEO Transponder / Regenerative Payload",
            "protocol": "Keplerian Orbit Mesh",
            "status": "orbiting",
            "details": f"Altitude: {link_estimate.satellite.altitude_km if link_estimate.satellite else 550} km",
        },
        {
            "step": 4,
            "node": f"Feeder Gateway: {best_gateway.name if best_gateway else 'Ground Gateway'}",
            "role": "Ka-Band Ground Teleport",
            "protocol": "Feeder Link 28.5 GHz Ka-band High-Speed Trunk",
            "status": "operational",
            "details": f"Capacity: {best_gateway.downlink_capacity_gbps if best_gateway else 40} Gbps downlink",
        },
        {
            "step": 5,
            "node": "Global Internet Backbone",
            "role": "Core Network Packet Gateway (P-GW/UPF)",
            "protocol": "IPv4 / IPv6 BGP Routing",
            "status": "online",
            "details": "Public Cloud & Web Services Transit",
        },
    ]

    # 4. Last Connectivity Test Record
    last_test = db.scalars(
        select(ConnectivityTest)
        .where(ConnectivityTest.user_id == user.id)
        .order_by(desc(ConnectivityTest.created_at))
        .limit(1)
    ).first()

    last_test_dict = None
    if last_test:
        last_test_dict = {
            "id": str(last_test.id),
            "ping_latency_ms": last_test.ping_latency_ms,
            "download_speed_mbps": last_test.download_speed_mbps,
            "upload_speed_mbps": last_test.upload_speed_mbps,
            "created_at": last_test.created_at.isoformat(),
        }

    # Combined Simulated and Measured Metrics
    metrics = {
        "latency_ms": round(link_estimate.latency_ms if link_estimate.latency_ms > 0 else 28.0, 1),
        "upload_speed_mbps": round(link_estimate.upload_mbps if link_estimate.upload_mbps > 0 else 1.5, 2),
        "download_speed_mbps": round(link_estimate.download_mbps if link_estimate.download_mbps > 0 else 8.5, 2),
        "packet_loss_percent": round(link_estimate.packet_loss if link_estimate.packet_loss < 100 else 1.0, 2),
        "signal_strength_dbm": round(link_estimate.signal_strength, 1),
        "carrier_c_n0_db_hz": round(link_estimate.c_n0_db_hz, 1),
    }

    return DirectToDeviceDashboardResponse(
        mobile_device_status={
            "platform": platform,
            "online_status": "online",
            "ip_address": "127.0.0.1",
            "battery_level_percent": 88,
            "coordinates": {"latitude_deg": latitude_deg, "longitude_deg": longitude_deg},
        },
        internet_availability={
            "cellular_online": True,
            "d2d_satellite_available": is_sat_visible,
            "active_link_mode": "Direct-to-Device Satellite Link" if is_sat_visible else "Terrestrial Cellular Fallback",
        },
        selected_satellite=sat_info,
        satellite_visibility=sat_visibility,
        gateway_status=gw_info,
        simulated_routing_path=routing_path,
        metrics=metrics,
        last_connectivity_test=last_test_dict,
        prototype_disclaimer="Simulated Direct-to-Device RF architecture. Does not claim physical satellite transmission without verified spacecraft transceiver hardware.",
    )
