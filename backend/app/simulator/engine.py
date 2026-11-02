import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.models.models import Satellite

EARTH_RADIUS_KM = 6371.0
EARTH_MU_KM3_S2 = 398600.4418
EARTH_ROTATION_RAD_S = 7.2921159e-5
REFERENCE_EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class LinkEstimate:
    satellite: Satellite | None
    elevation_deg: float
    distance_km: float
    signal_strength: float
    latency_ms: float
    packet_loss: float
    download_mbps: float
    upload_mbps: float
    visible: bool


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _satellite_position(satellite: Satellite, at: datetime) -> tuple[float, float, float]:
    radius = EARTH_RADIUS_KM + satellite.altitude_km
    mean_motion = math.sqrt(EARTH_MU_KM3_S2 / radius**3)
    elapsed_seconds = (at - REFERENCE_EPOCH).total_seconds()
    anomaly = math.radians(satellite.phase_deg) + mean_motion * elapsed_seconds
    inclination = math.radians(satellite.inclination_deg)
    raan = math.radians(satellite.raan_deg)
    x_orbit = radius * math.cos(anomaly)
    y_orbit = radius * math.sin(anomaly)
    x_inertial = x_orbit * math.cos(raan) - y_orbit * math.sin(raan) * math.cos(inclination)
    y_inertial = x_orbit * math.sin(raan) + y_orbit * math.cos(raan) * math.cos(inclination)
    z_inertial = y_orbit * math.sin(inclination)
    earth_angle = EARTH_ROTATION_RAD_S * elapsed_seconds
    return (
        x_inertial * math.cos(earth_angle) + y_inertial * math.sin(earth_angle),
        -x_inertial * math.sin(earth_angle) + y_inertial * math.cos(earth_angle),
        z_inertial,
    )


def estimate_link(
    satellites: Iterable[Satellite],
    latitude_deg: float,
    longitude_deg: float,
    at: datetime | None = None,
) -> LinkEstimate:
    """Estimate geometric visibility and illustrative link metrics; not measured RF performance."""
    at = at or datetime.now(timezone.utc)
    lat = math.radians(latitude_deg)
    lon = math.radians(longitude_deg)
    observer = (
        EARTH_RADIUS_KM * math.cos(lat) * math.cos(lon),
        EARTH_RADIUS_KM * math.cos(lat) * math.sin(lon),
        EARTH_RADIUS_KM * math.sin(lat),
    )
    up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
    best: LinkEstimate | None = None
    for satellite in satellites:
        position = _satellite_position(satellite, at)
        line_of_sight = tuple(p - o for p, o in zip(position, observer))
        distance = math.sqrt(_dot(line_of_sight, line_of_sight))
        elevation = math.degrees(math.asin(max(-1.0, min(1.0, _dot(line_of_sight, up) / distance))))
        visible = elevation > 0 and satellite.status.lower() == "active"
        elevation_factor = max(0.0, min(1.0, math.sin(math.radians(elevation))))
        # A fixed illustrative 2 GHz link budget; no weather, antenna, spectrum or modem model.
        fspl_db = 20 * math.log10(max(distance, 1.0)) + 20 * math.log10(2000.0) + 32.44
        signal_dbm = -30.0 - fspl_db + 35.0
        if visible:
            latency = 2 * distance / 299.792458 + 18.0
            packet_loss = max(0.1, min(15.0, 5.0 * (1.0 - elevation_factor)))
            download = round(20.0 * elevation_factor, 2)
            upload = round(5.0 * elevation_factor, 2)
        else:
            latency, packet_loss, download, upload = 0.0, 100.0, 0.0, 0.0
        candidate = LinkEstimate(
            satellite=satellite,
            elevation_deg=round(elevation, 2),
            distance_km=round(distance, 2),
            signal_strength=round(signal_dbm, 2),
            latency_ms=round(latency, 2),
            packet_loss=round(packet_loss, 2),
            download_mbps=download,
            upload_mbps=upload,
            visible=visible,
        )
        if best is None or candidate.elevation_deg > best.elevation_deg:
            best = candidate
    if best is not None:
        return best
    return LinkEstimate(None, -90.0, 0.0, -160.0, 0.0, 100.0, 0.0, 0.0, False)
