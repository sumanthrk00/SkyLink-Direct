"""Coordinate transformations and WGS-84 reference ellipsoid calculations.

Standards:
- WGS-84 reference ellipsoid (semi-major axis a = 6378.137 km, 1/f = 298.257223563).
- True/Mean Greenwich Sidereal Time (GMST) for ECI <-> ECEF rotating frame transforms.
- Bowring closed-form algorithm for ECEF to geodetic coordinates.
- Topocentric East-North-Up (ENU) horizon frame for observer elevation, azimuth, and range-rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

# WGS-84 Ellipsoid constants
WGS84_A_KM: float = 6378.137
WGS84_F: float = 1.0 / 298.257223563
WGS84_B_KM: float = WGS84_A_KM * (1.0 - WGS84_F)
WGS84_E2: float = 2.0 * WGS84_F - (WGS84_F**2)  # 0.00669437999014
WGS84_E_PRIME2: float = (WGS84_A_KM**2 - WGS84_B_KM**2) / (WGS84_B_KM**2)

# Earth angular rotation rate (rad/s, nominal WGS-84)
EARTH_ROTATION_RAD_S: float = 7.2921150e-5
# Reference epoch used for continuous time relative to baseline: 2024-01-01 00:00:00 UTC
REFERENCE_EPOCH: datetime = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class TopocentricMetrics:
    """Observer topocentric look-angles and range."""

    elevation_deg: float
    azimuth_deg: float
    distance_km: float
    range_rate_km_s: float
    east_km: float
    north_km: float
    up_km: float


def gmst_from_datetime(dt: datetime) -> float:
    """Calculate Greenwich Mean Sidereal Time (GMST) in radians for a given UTC datetime.

    Uses the IAU-82 expression with elapsed Julian centuries from epoch J2000.0.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_epoch_s = dt.timestamp()
    # Julian date: 1970-01-01 00:00:00 UTC corresponds to JD 2440587.5
    jd = 2440587.5 + (utc_epoch_s / 86400.0)
    d = jd - 2451545.0  # Days since J2000.0
    t = d / 36525.0

    gmst_deg = 280.46061837 + 360.98564736629 * d + 0.000387933 * (t**2) - ((t**3) / 38710000.0)
    return math.radians(gmst_deg % 360.0)


def eci_to_ecef(
    r_eci: tuple[float, float, float],
    v_eci: tuple[float, float, float] | None = None,
    gmst_rad: float = 0.0,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Convert position and velocity from Earth-Centered Inertial (ECI) to Earth-Centered Earth-Fixed (ECEF).

    Accounts for Earth rotation angle theta and Coriolis transport term (omega_E x r_ecef).
    """
    cos_t, sin_t = math.cos(gmst_rad), math.sin(gmst_rad)
    x_eci, y_eci, z_eci = r_eci

    x_ecef = cos_t * x_eci + sin_t * y_eci
    y_ecef = -sin_t * x_eci + cos_t * y_eci
    z_ecef = z_eci
    r_ecef = (x_ecef, y_ecef, z_ecef)

    if v_eci is None:
        v_ecef = (0.0, 0.0, 0.0)
    else:
        vx_eci, vy_eci, vz_eci = v_eci
        # R_z(theta) * v_eci
        vx_rot = cos_t * vx_eci + sin_t * vy_eci
        vy_rot = -sin_t * vx_eci + cos_t * vy_eci
        vz_rot = vz_eci
        # Velocity in rotating frame: v_ecef = R_z * v_eci - omega x r_ecef
        # omega x r = (-omega * y_ecef, omega * x_ecef, 0)
        v_ecef = (
            vx_rot + EARTH_ROTATION_RAD_S * y_ecef,
            vy_rot - EARTH_ROTATION_RAD_S * x_ecef,
            vz_rot,
        )

    return r_ecef, v_ecef


def geodetic_to_ecef(lat_deg: float, lon_deg: float, altitude_km: float = 0.0) -> tuple[float, float, float]:
    """Convert WGS-84 Geodetic coordinates (latitude, longitude, altitude) to ECEF Cartesian (km)."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)

    # Prime vertical radius of curvature
    n = WGS84_A_KM / math.sqrt(1.0 - WGS84_E2 * (sin_lat**2))

    x = (n + altitude_km) * cos_lat * math.cos(lon)
    y = (n + altitude_km) * cos_lat * math.sin(lon)
    z = (n * (1.0 - WGS84_E2) + altitude_km) * sin_lat
    return x, y, z


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert ECEF coordinates (km) to WGS-84 Geodetic coordinates (lat_deg, lon_deg, alt_km).

    Uses Bowring's closed-form algorithm (accurate to within millimeters globally).
    """
    p = math.sqrt(x**2 + y**2)
    if p < 1e-6:
        # Near poles
        lat_deg = 90.0 if z >= 0 else -90.0
        lon_deg = 0.0
        alt_km = abs(z) - WGS84_B_KM
        return lat_deg, lon_deg, alt_km

    theta = math.atan2(z * WGS84_A_KM, p * WGS84_B_KM)
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)

    lat = math.atan2(
        z + WGS84_E_PRIME2 * WGS84_B_KM * (sin_t**3),
        p - WGS84_E2 * WGS84_A_KM * (cos_t**3),
    )
    lon = math.atan2(y, x)

    sin_lat = math.sin(lat)
    n = WGS84_A_KM / math.sqrt(1.0 - WGS84_E2 * (sin_lat**2))
    alt_km = (p / math.cos(lat)) - n

    return math.degrees(lat), math.degrees(lon), alt_km


def calculate_topocentric(
    obs_lat_deg: float,
    obs_lon_deg: float,
    obs_alt_km: float,
    sat_ecef: tuple[float, float, float],
    sat_v_ecef: tuple[float, float, float] | None = None,
) -> TopocentricMetrics:
    """Calculate topocentric East-North-Up (ENU) metrics from an observer to a satellite."""
    obs_ecef = geodetic_to_ecef(obs_lat_deg, obs_lon_deg, obs_alt_km)
    dx = sat_ecef[0] - obs_ecef[0]
    dy = sat_ecef[1] - obs_ecef[1]
    dz = sat_ecef[2] - obs_ecef[2]

    distance = math.sqrt(dx**2 + dy**2 + dz**2)
    if distance < 1e-6:
        return TopocentricMetrics(90.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    lat = math.radians(obs_lat_deg)
    lon = math.radians(obs_lon_deg)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)

    # Rotation from ECEF to ENU
    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

    elevation = math.degrees(math.asin(max(-1.0, min(1.0, up / distance))))
    azimuth = math.degrees(math.atan2(east, north)) % 360.0

    # Range rate (dr/dt = (rho_vector . v_relative) / distance)
    if sat_v_ecef is not None:
        range_rate = (dx * sat_v_ecef[0] + dy * sat_v_ecef[1] + dz * sat_v_ecef[2]) / distance
    else:
        range_rate = 0.0

    return TopocentricMetrics(
        elevation_deg=round(elevation, 3),
        azimuth_deg=round(azimuth, 3),
        distance_km=round(distance, 3),
        range_rate_km_s=round(range_rate, 4),
        east_km=round(east, 3),
        north_km=round(north, 3),
        up_km=round(up, 3),
    )

