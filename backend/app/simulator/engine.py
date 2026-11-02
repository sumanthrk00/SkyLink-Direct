"""High-fidelity satellite network simulation and visibility engine.

Combines:
- Keplerian two-body mechanics and J2 perturbation propagation (orbit.py)
- WGS-84 reference ellipsoid and topocentric ENU horizon transformations (coordinates.py)
- 3GPP NTN RF link budget, Doppler shift, and atmospheric path loss (rf.py)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.models.models import Satellite
from app.simulator.coordinates import (
    EARTH_ROTATION_RAD_S,
    WGS84_A_KM,
    calculate_topocentric,
    ecef_to_geodetic,
    eci_to_ecef,
)
from app.simulator.orbit import (
    DEFAULT_EPOCH,
    EARTH_MU_KM3_S2,
    EARTH_RADIUS_KM,
    KeplerianElements,
    propagate_kepler,
)
from app.simulator.rf import (
    apparent_elevation_deg,
    compute_link_budget,
)

REFERENCE_EPOCH = DEFAULT_EPOCH


@dataclass(frozen=True)
class LinkEstimate:
    """Visibility and RF link estimate for an observer location."""

    satellite: Satellite | None
    elevation_deg: float
    distance_km: float
    signal_strength: float
    latency_ms: float
    packet_loss: float
    download_mbps: float
    upload_mbps: float
    visible: bool
    azimuth_deg: float = 0.0
    apparent_elevation_deg: float = 0.0
    range_rate_km_s: float = 0.0
    doppler_shift_hz: float = 0.0
    c_n0_db_hz: float = 0.0
    snr_db: float = 0.0


@dataclass(frozen=True)
class SatellitePass:
    """Predicted overhead pass of a satellite above observer's horizon."""

    satellite_id: str
    satellite_name: str
    aos_utc: datetime  # Acquisition of Signal
    tca_utc: datetime  # Time of Closest Approach (peak elevation)
    los_utc: datetime  # Loss of Signal
    max_elevation_deg: float
    duration_seconds: int
    tca_distance_km: float
    tca_azimuth_deg: float


def satellite_to_elements(satellite: Satellite) -> KeplerianElements:
    """Convert an ORM Satellite model into Keplerian orbital elements."""
    semi_major_axis_km = WGS84_A_KM + satellite.altitude_km
    return KeplerianElements(
        semi_major_axis_km=semi_major_axis_km,
        eccentricity=0.0,  # Circular LEO constellation design
        inclination_deg=satellite.inclination_deg,
        raan_deg=satellite.raan_deg,
        arg_periapsis_deg=0.0,
        mean_anomaly_epoch_deg=satellite.phase_deg,
        epoch=REFERENCE_EPOCH,
    )


def satellite_position_ecef(
    satellite: Satellite,
    at: datetime,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Compute ECEF position (km) and velocity (km/s) of a satellite at given UTC time."""
    elements = satellite_to_elements(satellite)
    r_eci, v_eci = propagate_kepler(elements, at, include_j2=True)
    # Earth rotation angle relative to reference epoch
    elapsed_seconds = (at - REFERENCE_EPOCH).total_seconds()
    earth_angle = (EARTH_ROTATION_RAD_S * elapsed_seconds) % (2.0 * math.pi)
    return eci_to_ecef(r_eci, v_eci, earth_angle)


def satellite_subpoint(
    satellite: Satellite,
    at: datetime,
) -> tuple[float, float, float]:
    """Calculate sub-satellite point (latitude_deg, longitude_deg, altitude_km) on WGS-84 ellipsoid."""
    r_ecef, _ = satellite_position_ecef(satellite, at)
    lat, lon, alt = ecef_to_geodetic(r_ecef[0], r_ecef[1], r_ecef[2])
    return round(lat, 4), round(lon, 4), round(alt, 2)


def estimate_link(
    satellites: Iterable[Satellite],
    latitude_deg: float,
    longitude_deg: float,
    at: datetime | None = None,
    altitude_km: float = 0.0,
) -> LinkEstimate:
    """Estimate geometric visibility, Doppler, and 3GPP NTN link budget.

    Returns the best available satellite candidate with the highest elevation.
    """
    at = at or datetime.now(timezone.utc)
    best_candidate: LinkEstimate | None = None

    for satellite in satellites:
        if satellite.status.lower() != "active":
            continue

        r_ecef, v_ecef = satellite_position_ecef(satellite, at)
        topocentric = calculate_topocentric(
            obs_lat_deg=latitude_deg,
            obs_lon_deg=longitude_deg,
            obs_alt_km=altitude_km,
            sat_ecef=r_ecef,
            sat_v_ecef=v_ecef,
        )

        rf = compute_link_budget(
            distance_km=topocentric.distance_km,
            elevation_deg=topocentric.elevation_deg,
            range_rate_km_s=topocentric.range_rate_km_s,
        )

        visible = topocentric.elevation_deg > 0.0

        candidate = LinkEstimate(
            satellite=satellite,
            elevation_deg=topocentric.elevation_deg,
            distance_km=topocentric.distance_km,
            signal_strength=rf.received_power_dbm,
            latency_ms=rf.latency_ms,
            packet_loss=rf.packet_loss_percent,
            download_mbps=rf.download_mbps,
            upload_mbps=rf.upload_mbps,
            visible=visible,
            azimuth_deg=topocentric.azimuth_deg,
            apparent_elevation_deg=apparent_elevation_deg(topocentric.elevation_deg),
            range_rate_km_s=topocentric.range_rate_km_s,
            doppler_shift_hz=rf.doppler_shift_hz,
            c_n0_db_hz=rf.c_n0_db_hz,
            snr_db=rf.snr_db,
        )

        if best_candidate is None or candidate.elevation_deg > best_candidate.elevation_deg:
            best_candidate = candidate

    if best_candidate is not None:
        return best_candidate

    return LinkEstimate(
        satellite=None,
        elevation_deg=-90.0,
        distance_km=0.0,
        signal_strength=-160.0,
        latency_ms=0.0,
        packet_loss=100.0,
        download_mbps=0.0,
        upload_mbps=0.0,
        visible=False,
    )


def predict_passes(
    satellites: Iterable[Satellite],
    latitude_deg: float,
    longitude_deg: float,
    start_time: datetime | None = None,
    duration_hours: float = 6.0,
    step_seconds: int = 30,
    min_elevation_deg: float = 10.0,
) -> list[SatellitePass]:
    """Predict satellite overhead passes above the observer's elevation mask threshold."""
    start = start_time or datetime.now(timezone.utc)
    end = start + timedelta(hours=duration_hours)
    passes: list[SatellitePass] = []

    active_sats = [s for s in satellites if s.status.lower() == "active"]

    for sat in active_sats:
        curr_time = start
        in_pass = False
        aos: datetime | None = None
        max_el = -90.0
        tca: datetime | None = None
        tca_dist = 0.0
        tca_az = 0.0

        while curr_time <= end:
            r_ecef, v_ecef = satellite_position_ecef(sat, curr_time)
            topo = calculate_topocentric(latitude_deg, longitude_deg, 0.0, r_ecef, v_ecef)

            if topo.elevation_deg >= min_elevation_deg:
                if not in_pass:
                    in_pass = True
                    aos = curr_time
                    max_el = topo.elevation_deg
                    tca = curr_time
                    tca_dist = topo.distance_km
                    tca_az = topo.azimuth_deg
                else:
                    if topo.elevation_deg > max_el:
                        max_el = topo.elevation_deg
                        tca = curr_time
                        tca_dist = topo.distance_km
                        tca_az = topo.azimuth_deg
            elif in_pass:
                # Pass completed (LOS)
                los = curr_time
                if aos and tca and max_el >= min_elevation_deg:
                    passes.append(
                        SatellitePass(
                            satellite_id=str(sat.id),
                            satellite_name=sat.name,
                            aos_utc=aos,
                            tca_utc=tca,
                            los_utc=los,
                            max_elevation_deg=round(max_el, 2),
                            duration_seconds=int((los - aos).total_seconds()),
                            tca_distance_km=round(tca_dist, 2),
                            tca_azimuth_deg=round(tca_az, 2),
                        )
                    )
                in_pass = False
                aos = None
                max_el = -90.0

            curr_time += timedelta(seconds=step_seconds)

    # Sort passes by acquisition of signal (AOS)
    passes.sort(key=lambda p: p.aos_utc)
    return passes
