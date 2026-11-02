"""High-precision Keplerian orbit propagation and perturbation modeling.

Models:
- Full Keplerian two-body problem with numerical Newton-Raphson Kepler equation solver.
- WGS-84 / EGM96 Earth gravitational parameters.
- J2 zonal harmonic secular oblateness perturbations (nodal regression & apsidal precession).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

# WGS-84 / EGM96 Gravitational parameter for Earth (km^3 / s^2)
EARTH_MU_KM3_S2: float = 398600.4418
# Earth equatorial radius (km)
EARTH_RADIUS_KM: float = 6378.137
# Earth J2 zonal harmonic coefficient (un-normalized)
EARTH_J2: float = 1.08262668e-3
# Standard reference epoch: 2024-01-01 00:00:00 UTC
DEFAULT_EPOCH: datetime = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class KeplerianElements:
    """Orbital elements defining a satellite trajectory."""

    semi_major_axis_km: float
    eccentricity: float = 0.0
    inclination_deg: float = 53.0
    raan_deg: float = 0.0
    arg_periapsis_deg: float = 0.0
    mean_anomaly_epoch_deg: float = 0.0
    epoch: datetime = DEFAULT_EPOCH

    @property
    def mean_motion_rad_s(self) -> float:
        """Kepler's third law: n = sqrt(mu / a^3)."""
        return math.sqrt(EARTH_MU_KM3_S2 / (self.semi_major_axis_km**3))

    @property
    def orbital_period_s(self) -> float:
        """Orbital period in seconds: T = 2 * pi * sqrt(a^3 / mu)."""
        return 2.0 * math.pi / self.mean_motion_rad_s


def solve_kepler(mean_anomaly_rad: float, eccentricity: float, tolerance: float = 1e-11, max_iter: int = 60) -> float:
    """Solve Kepler's equation M = E - e*sin(E) for Eccentric Anomaly E using Newton-Raphson."""
    e = max(0.0, min(0.999999, eccentricity))
    m = mean_anomaly_rad % (2.0 * math.pi)

    # Initial guess
    e_curr = m + e * math.sin(m) if e < 0.8 else math.pi

    for _ in range(max_iter):
        f = e_curr - e * math.sin(e_curr) - m
        f_prime = 1.0 - e * math.cos(e_curr)
        if abs(f_prime) < 1e-14:
            break
        delta = f / f_prime
        e_curr -= delta
        if abs(delta) < tolerance:
            break

    return e_curr


def true_anomaly_from_eccentric(eccentric_anomaly_rad: float, eccentricity: float) -> float:
    """Calculate true anomaly nu from eccentric anomaly E."""
    e = max(0.0, min(0.999999, eccentricity))
    half_e = eccentric_anomaly_rad / 2.0
    sin_half_nu = math.sqrt(1.0 + e) * math.sin(half_e)
    cos_half_nu = math.sqrt(1.0 - e) * math.cos(half_e)
    return 2.0 * math.atan2(sin_half_nu, cos_half_nu)


def j2_secular_drift(semi_major_axis_km: float, eccentricity: float, inclination_deg: float) -> tuple[float, float]:
    """Calculate secular J2 nodal regression (d_Omega/dt) and perigee precession (d_omega/dt) in rad/s.

    Returns:
        tuple[float, float]: (raan_rate_rad_s, perigee_rate_rad_s)
    """
    p = semi_major_axis_km * (1.0 - eccentricity**2)
    n = math.sqrt(EARTH_MU_KM3_S2 / (semi_major_axis_km**3))
    inc = math.radians(inclination_deg)
    scaling = 1.5 * EARTH_J2 * ((EARTH_RADIUS_KM / p) ** 2) * n

    raan_rate = -scaling * math.cos(inc)
    perigee_rate = 0.5 * scaling * (5.0 * (math.cos(inc) ** 2) - 1.0)
    return raan_rate, perigee_rate


def propagate_kepler(
    elements: KeplerianElements,
    at: datetime,
    include_j2: bool = True,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Propagate Keplerian orbit to target datetime.

    Returns:
        tuple[tuple[float, float, float], tuple[float, float, float]]:
            (r_eci_km, v_eci_km_s) in Earth-Centered Inertial (ECI) coordinate frame.
    """
    dt_seconds = (at - elements.epoch).total_seconds()
    n = elements.mean_motion_rad_s
    mean_anomaly = math.radians(elements.mean_anomaly_epoch_deg) + n * dt_seconds

    raan = math.radians(elements.raan_deg)
    arg_p = math.radians(elements.arg_periapsis_deg)
    inc = math.radians(elements.inclination_deg)

    if include_j2:
        d_raan, d_arg_p = j2_secular_drift(elements.semi_major_axis_km, elements.eccentricity, elements.inclination_deg)
        raan += d_raan * dt_seconds
        arg_p += d_arg_p * dt_seconds

    eccentric_anomaly = solve_kepler(mean_anomaly, elements.eccentricity)
    nu = true_anomaly_from_eccentric(eccentric_anomaly, elements.eccentricity)

    # Perifocal distance and parameter
    p = elements.semi_major_axis_km * (1.0 - elements.eccentricity**2)
    radius = p / (1.0 + elements.eccentricity * math.cos(nu))

    # Position and velocity vectors in perifocal PQW frame
    r_pqw = (radius * math.cos(nu), radius * math.sin(nu), 0.0)
    sqrt_mu_p = math.sqrt(EARTH_MU_KM3_S2 / p)
    v_pqw = (-sqrt_mu_p * math.sin(nu), sqrt_mu_p * (elements.eccentricity + math.cos(nu)), 0.0)

    # Rotation matrix from perifocal PQW to ECI frame
    cos_o, sin_o = math.cos(raan), math.sin(raan)
    cos_w, sin_w = math.cos(arg_p), math.sin(arg_p)
    cos_i, sin_i = math.cos(inc), math.sin(inc)

    # P unit vector (towards periapsis)
    px = cos_o * cos_w - sin_o * sin_w * cos_i
    py = sin_o * cos_w + cos_o * sin_w * cos_i
    pz = sin_w * sin_i

    # Q unit vector (perpendicular to P in orbital plane)
    qx = -cos_o * sin_w - sin_o * cos_w * cos_i
    qy = -sin_o * sin_w + cos_o * cos_w * cos_i
    qz = cos_w * sin_i

    r_eci = (
        r_pqw[0] * px + r_pqw[1] * qx,
        r_pqw[0] * py + r_pqw[1] * qy,
        r_pqw[0] * pz + r_pqw[1] * qz,
    )

    v_eci = (
        v_pqw[0] * px + v_pqw[1] * qx,
        v_pqw[0] * py + v_pqw[1] * qy,
        v_pqw[0] * pz + v_pqw[1] * qz,
    )

    return r_eci, v_eci

