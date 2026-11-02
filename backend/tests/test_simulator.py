"""Unit tests for Keplerian orbit propagation, WGS-84 coordinate transforms, Doppler shifts, and RF link budget."""

import math
from datetime import datetime, timezone

import pytest

from app.models.models import Satellite
from app.simulator.coordinates import (
    calculate_topocentric,
    ecef_to_geodetic,
    geodetic_to_ecef,
    gmst_from_datetime,
)
from app.simulator.engine import estimate_link, predict_passes, satellite_subpoint
from app.simulator.orbit import (
    KeplerianElements,
    j2_secular_drift,
    propagate_kepler,
    solve_kepler,
    true_anomaly_from_eccentric,
)
from app.simulator.rf import (
    apparent_elevation_deg,
    calculate_doppler_shift,
    compute_link_budget,
    free_space_path_loss_db,
)


def test_solve_kepler_and_true_anomaly():
    # Circular orbit: E == M, nu == M
    m_circ = math.radians(45.0)
    e_circ = solve_kepler(m_circ, 0.0)
    assert math.isclose(e_circ, m_circ, abs_tol=1e-10)
    nu_circ = true_anomaly_from_eccentric(e_circ, 0.0)
    assert math.isclose(nu_circ, m_circ, abs_tol=1e-10)

    # Eccentric orbit: e = 0.2
    ecc = 0.2
    for angle_deg in [10.0, 60.0, 120.0, 240.0, 330.0]:
        m = math.radians(angle_deg)
        e_sol = solve_kepler(m, ecc)
        recalculated_m = e_sol - ecc * math.sin(e_sol)
        assert math.isclose(recalculated_m, m, abs_tol=1e-9)


def test_j2_secular_drift():
    # LEO orbit at 550 km, 53 degrees inclination
    a_km = 6378.137 + 550.0
    raan_rate, perigee_rate = j2_secular_drift(a_km, 0.0, 53.0)
    # Prograde orbit (i < 90 deg) must have retrograde nodal regression (raan_rate < 0)
    assert raan_rate < 0.0
    # Daily drift in degrees
    daily_raan_deg = math.degrees(raan_rate) * 86400.0
    # Expected Starlink/LEO 53 deg nodal regression is approx -5 to -6 deg/day
    assert -7.0 < daily_raan_deg < -4.0


def test_wgs84_geodetic_ecef_roundtrip():
    test_locations = [
        (12.9716, 77.5946, 0.920),   # Bangalore, India
        (37.7749, -122.4194, 0.030), # San Francisco, USA
        (0.0, 0.0, 0.0),             # Prime meridian equator
        (90.0, 0.0, 0.0),            # North pole
        (-90.0, 0.0, 0.0),           # South pole
    ]
    for lat, lon, alt in test_locations:
        x, y, z = geodetic_to_ecef(lat, lon, alt)
        lat_back, lon_back, alt_back = ecef_to_geodetic(x, y, z)
        assert math.isclose(lat, lat_back, abs_tol=1e-4)
        if abs(lat) < 89.0:  # Longitude singularity at poles
            assert math.isclose(lon, lon_back, abs_tol=1e-4)
        assert math.isclose(alt, alt_back, abs_tol=1e-3)


def test_doppler_shift_and_fspl():
    # 2 GHz carrier, approaching at 5 km/s
    carrier_hz = 2000e6
    range_rate = -5.0  # Approaching (blueshift)
    doppler = calculate_doppler_shift(carrier_hz, range_rate)
    assert doppler > 0  # Frequency increases
    # Approx 33.3 kHz
    assert 30000.0 < doppler < 35000.0

    # FSPL check: at 1000 km, 2000 MHz
    fspl = free_space_path_loss_db(1000.0, 2000.0)
    # 20*log10(1000) + 20*log10(2000) + 32.448 = 60 + 66.02 + 32.448 = 158.468 dB
    assert math.isclose(fspl, 158.468, abs_tol=0.1)


def test_apparent_elevation_refraction():
    # At zenith, refraction is negligible
    assert math.isclose(apparent_elevation_deg(90.0), 90.0, abs_tol=0.05)
    # Near horizon (e.g. 5 deg), refraction should increase apparent elevation
    app_5 = apparent_elevation_deg(5.0)
    assert app_5 > 5.0
    assert 5.1 < app_5 < 5.3


def test_predict_passes_for_constellation():
    # Create sample synthetic constellation
    satellites = [
        Satellite(
            name=f"SL-TEST-{i}",
            orbit_type="LEO",
            altitude_km=550.0,
            status="active",
            inclination_deg=53.0,
            raan_deg=float(i * 60),
            phase_deg=float(i * 30),
        )
        for i in range(6)
    ]
    start = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    passes = predict_passes(satellites, 12.9716, 77.5946, start_time=start, duration_hours=6.0, min_elevation_deg=15.0)
    assert len(passes) > 0
    for p in passes:
        assert p.aos_utc < p.tca_utc < p.los_utc
        assert p.max_elevation_deg >= 15.0
        assert p.duration_seconds > 0
        assert p.tca_distance_km > 500.0

