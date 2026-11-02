# SkyLink Direct — Development Roadmap & Technical Plan

This document outlines the phased development stages for expanding the SkyLink Direct prototype from an illustrative demonstrator into a high-fidelity satellite connectivity simulator.

---

## Phase 1: High-Precision Orbital Simulation & Propagation
- **Current State:** Circular orbit approximation with Keplerian mean motion referenced to epoch 2024-01-01 UTC.
- **Stage 1 Implementation:**
  - Introduce full Keplerian orbital elements: semi-major axis ($a$), eccentricity ($e$), inclination ($i$), Right Ascension of the Ascending Node ($\Omega$), argument of periapsis ($\omega$), and true/mean anomaly ($M$).
  - Implement numerical solving of Kepler's Equation for eccentric orbits ($M = E - e \sin E$) via Newton-Raphson iteration.
  - Add optional TLE (Two-Line Element) parsing and SGP4 (Simplified General Perturbations-4) propagation integration via the `sgp4` library for real-world space debris and satellite tracking compatibility.
  - Document assumptions: J2 zonal harmonic oblateness perturbation ($J_2 = 1.08263 \times 10^{-3}$) causing nodal regression and apsidal precession.

---

## Phase 2: Satellite Position Calculation (ECI to ECEF)
- **Current State:** Fixed Earth diurnal rotation applied directly to simplified orbital plane vectors.
- **Stage 2 Implementation:**
  - Standardize coordinate frame transformations using IAU SOFA / IERS standards:
    - Celestial Intermediate Origin (CIO) / Earth-Centered Inertial (ECI, GCRS).
    - True of Date / Greenwich Mean Sidereal Time (GMST) accounting for Earth's axial precession and nutation.
    - WGS-84 reference ellipsoid ($a = 6378.137\text{ km}$, $f = 1/298.257223563$) replacing the spherical Earth approximation.
  - Compute satellite sub-satellite points (geodetic latitude, longitude, and height above ellipsoid).

---

## Phase 3: Location-Based Visibility & Pass Prediction
- **Current State:** Point-in-time snapshot check for visibility from observer.
- **Stage 3 Implementation:**
  - Implement **pass prediction**: calculate Rise-Set times (AOS - Acquisition of Signal, TCA - Time of Closest Approach, LOS - Loss of Signal) over customizable forward lookahead windows (e.g., next 12, 24, 48 hours).
  - Support minimum elevation mask thresholds ($5^\circ$, $10^\circ$, $20^\circ$) reflecting urban canyon, terrain, or terminal antenna constraints.
  - Output azimuth and elevation track tables for directional ground antenna tracking.

---

## Phase 4: Elevation-Angle & Atmospheric Refraction Modeling
- **Current State:** Geometric trigonometric elevation angle above spherical tangent plane.
- **Stage 4 Implementation:**
  - Compute True vs. Apparent Elevation including tropospheric refraction (ITU-R P.834 / Saastamoinen model).
  - Calculate Doppler shift caused by satellite relative line-of-sight velocity:
    $$\Delta f = f_0 \frac{\vec{v}_{rel} \cdot \hat{\rho}}{c}$$
    Essential for direct-to-device modem synchronization and receiver frequency correction.

---

## Phase 5: Radio-Link Budget & RF Channel Modeling
- **Current State:** Simplified Free Space Path Loss (FSPL) at 2.0 GHz with elevation-scaled throughput heuristics.
- **Stage 5 Implementation:**
  - Implement comprehensive ITU-R P.618 and 3GPP TR 38.811 (NTN - Non-Terrestrial Networks) channel model:
    - **Free Space Path Loss (FSPL):** Exact distance-frequency calculation across L, S, Ku, and Ka bands.
    - **Atmospheric Absorption:** Oxygen and water vapor attenuation (ITU-R P.676).
    - **Tropospheric Scintillation & Rain Attenuation:** ITU-R P.838 / P.618 for frequencies above 10 GHz.
    - **Ionospheric Scintillation and Faraday Rotation:** For L/S band mobile satellite service.
    - **Shadowing & Multipath:** Urban, suburban, and rural line-of-sight probability distributions (Loo / Lutz distribution).
  - Calculate Signal-to-Noise Ratio (SNR) and Carrier-to-Noise-Density ($C/N_0$):
    $$\frac{C}{N_0} = EIRP - L_{path} + \left(\frac{G}{T}\right) - k$$
  - Map $C/N_0$ directly to 3GPP 5G NTN Modulation and Coding Schemes (MCS, QPSK up to 64-QAM) to compute realistic achievable bitrates.

---

## Phase 6: Ground-Station Management & Feeder Links
- **Current State:** `GroundStation` relational model and CRUD API in backend.
- **Stage 6 Implementation:**
  - Model feeder links (ground station to satellite backhaul) and inter-satellite links (ISL).
  - Implement ground station antenna steering limits and schedule contact windows.
  - Surface interactive ground station management tab in the web dashboard.

---

## Phase 7: Real-Time Network Monitoring & Live Telemetry
- **Current State:** Periodic REST polling.
- **Stage 7 Implementation:**
  - Implement WebSocket endpoint (`/ws/telemetry`) streaming live orbital positions and active session metrics at 1 Hz.
  - Dynamic 2D/3D orbital ground track visualization (using CesiumJS or Leaflet) displaying real-time footprint coverage circles.
  - Active session handover simulation when a satellite moves below the horizon and another acquires visibility.

---

## Phase 8: Administrative Dashboard & Multi-Tenancy
- **Current State:** Summary counts endpoint (`/admin/dashboard`).
- **Stage 8 Implementation:**
  - Detailed system health metrics (API response times, database connection pool, rate limiting triggers).
  - User and device fleet management (suspend, promote, view usage quotas).
  - Global constellation status controls (simulate satellite maintenance, orbit adjustments, de-orbiting).

---

## Phase 9: Simulation Reports & Data Export
- **Current State:** In-app table history.
- **Stage 9 Implementation:**
  - PDF and CSV export of simulation runs and signal pass predictions.
  - Detailed link budget breakdown reports (EIRP, FSPL, atmospheric losses, fade margin, receiver $G/T$, achieved throughput).
  - Shareable simulation permalinks with reproducible orbital timestamp configurations.

