"""RF propagation, Doppler shift, tropospheric refraction, and 3GPP NTN link budget.

Scientific Models:
- ITU-R P.525: Free Space Path Loss (FSPL) across L/S/Ku/Ka bands.
- Bennett / Saastamoinen model: Tropospheric refraction for apparent elevation.
- Doppler effect: Delta f = -f0 * (range_rate / c).
- ITU-R P.676: Atmospheric gaseous attenuation scaling.
- 3GPP TR 38.811: Non-Terrestrial Network (NTN) link budget and MCS (Modulation and Coding Scheme) mapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Speed of light in vacuum (km/s)
SPEED_OF_LIGHT_KM_S: float = 299792.458
# Boltzmann constant in dBW / (Hz * K)
BOLTZMANN_K_DBW: float = -228.60


@dataclass(frozen=True)
class RfLinkBudget:
    """Detailed radio frequency link budget computation results."""

    carrier_freq_mhz: float
    slant_range_km: float
    true_elevation_deg: float
    apparent_elevation_deg: float
    range_rate_km_s: float
    doppler_shift_hz: float
    fspl_db: float
    atmospheric_loss_db: float
    total_path_loss_db: float
    received_power_dbm: float
    c_n0_db_hz: float
    snr_db: float
    download_mbps: float
    upload_mbps: float
    latency_ms: float
    packet_loss_percent: float


def calculate_doppler_shift(carrier_freq_hz: float, range_rate_km_s: float) -> float:
    """Calculate Doppler frequency shift in Hz.

    Positive range_rate means satellite is moving away (redshift / negative frequency shift).
    Negative range_rate means satellite is approaching (blueshift / positive frequency shift).
    """
    return -(carrier_freq_hz * (range_rate_km_s / SPEED_OF_LIGHT_KM_S))


def free_space_path_loss_db(distance_km: float, freq_mhz: float) -> float:
    """Calculate Free Space Path Loss (FSPL) in dB using Friis transmission formula."""
    d = max(0.1, distance_km)
    f = max(1.0, freq_mhz)
    return 20.0 * math.log10(d) + 20.0 * math.log10(f) + 32.448


def apparent_elevation_deg(true_elevation_deg: float) -> float:
    """Calculate apparent elevation including atmospheric refraction using Bennett's formula."""
    if true_elevation_deg < -5.0:
        return true_elevation_deg
    el = max(0.0, true_elevation_deg)
    # Refraction in arcminutes
    refraction_arcmin = 1.02 / math.tan(math.radians(el + (10.3 / (el + 5.11))))
    return round(true_elevation_deg + (refraction_arcmin / 60.0), 3)


def atmospheric_loss_db(elevation_deg: float, freq_mhz: float) -> float:
    """Estimate atmospheric gaseous absorption (oxygen and water vapor) via ITU-R P.676 model approximation."""
    if elevation_deg <= 0:
        return 20.0
    # Zenith attenuation in dB: ~0.04 dB for S-band (2 GHz), higher for Ka band
    freq_ghz = freq_mhz / 1000.0
    zenith_db = 0.035 * (1.0 + 0.05 * (freq_ghz**1.2))
    # Airmass slant scaling: 1 / sin(elevation)
    effective_sin = math.sin(math.radians(max(3.0, elevation_deg)))
    airmass = 1.0 / effective_sin
    return round(zenith_db * airmass, 3)


def compute_link_budget(
    distance_km: float,
    elevation_deg: float,
    range_rate_km_s: float = 0.0,
    carrier_freq_mhz: float = 2000.0,
    satellite_eirp_dbw: float = 34.0,  # LEO multi-beam phased array spot
    user_gt_db_k: float = -26.0,  # Handheld terminal G/T (internal patch antenna)
    bandwidth_mhz: float = 5.0,  # 3GPP NTN standard 5 MHz channel
) -> RfLinkBudget:
    """Compute comprehensive 3GPP NTN radio link budget and achievable data rates."""
    fspl = free_space_path_loss_db(distance_km, carrier_freq_mhz)
    atm_loss = atmospheric_loss_db(elevation_deg, carrier_freq_mhz)
    total_loss = fspl + atm_loss

    carrier_freq_hz = carrier_freq_mhz * 1e6
    doppler = calculate_doppler_shift(carrier_freq_hz, range_rate_km_s)
    apparent_el = apparent_elevation_deg(elevation_deg)

    # Carrier-to-Noise Density (C/N0) = EIRP - L_total + G/T - k
    c_n0 = satellite_eirp_dbw - total_loss + user_gt_db_k - BOLTZMANN_K_DBW
    bandwidth_db_hz = 10.0 * math.log10(bandwidth_mhz * 1e6)
    snr = c_n0 - bandwidth_db_hz

    # Received signal strength indicator (RSSI / RSRP in dBm)
    # EIRP (dBW) - Total Loss (dB) + Rx Gain (approx 0 dBi) + 30 (to dBm)
    received_dbm = satellite_eirp_dbw - total_loss + 0.0 + 30.0

    # Propagation latency: two-way round trip time (RTT) + 3GPP NTN scheduling delay
    rtt_propagation_ms = 2.0 * (distance_km / SPEED_OF_LIGHT_KM_S) * 1000.0
    processing_delay_ms = 18.0  # Baseband, framing & terrestrial gateway processing
    total_latency_ms = round(rtt_propagation_ms + processing_delay_ms, 2)

    # Shannon-Hartley bounded NTN MCS throughput mapping
    is_visible = elevation_deg > 0.0
    if is_visible and snr > -6.0:
        # Elevation factor scales multipath / blockage immunity
        elevation_weight = max(0.1, min(1.0, math.sin(math.radians(max(0.1, elevation_deg)))))
        # Spectral efficiency (bps/Hz) clamped to 3GPP NTN MCS table (QPSK 1/3 up to 64-QAM)
        spectral_eff = max(0.2, min(3.8, 0.33 * math.log2(1.0 + 10.0 ** (max(0.0, snr) / 10.0))))
        raw_capacity_mbps = bandwidth_mhz * spectral_eff
        download = round(raw_capacity_mbps * elevation_weight * 0.85, 2)
        upload = round(download * 0.25, 2)
        packet_loss = round(max(0.05, min(12.0, 4.0 * (1.0 - elevation_weight) + max(0.0, (2.0 - snr) * 0.5))), 2)
    else:
        download, upload = 0.0, 0.0
        packet_loss = 100.0
        total_latency_ms = 0.0

    return RfLinkBudget(
        carrier_freq_mhz=carrier_freq_mhz,
        slant_range_km=round(distance_km, 2),
        true_elevation_deg=round(elevation_deg, 2),
        apparent_elevation_deg=apparent_el,
        range_rate_km_s=round(range_rate_km_s, 4),
        doppler_shift_hz=round(doppler, 1),
        fspl_db=round(fspl, 2),
        atmospheric_loss_db=atm_loss,
        total_path_loss_db=round(total_loss, 2),
        received_power_dbm=round(received_dbm, 2),
        c_n0_db_hz=round(c_n0, 2),
        snr_db=round(snr, 2),
        download_mbps=download,
        upload_mbps=upload,
        latency_ms=total_latency_ms,
        packet_loss_percent=packet_loss,
    )

