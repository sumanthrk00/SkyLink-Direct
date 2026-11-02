# SkyLink Direct — Testing Report

**Date of Execution:** 2026-11-02  
**Platform:** Windows 11 (Python 3.12.3, Node.js v22.x, SQLite 3)  
**Test Harness:** Pytest 8.3.5, Vitest 5.0.5, TypeScript 5.6.3 compiler  

---

## 1. Automated Test Results

### 1.1 Backend Test Suite (Pytest)
Command executed:
```powershell
.\.venv\Scripts\pytest -v
```
**Results:** **12 passed in 3.41s (100% success rate)**

| Test Name | Area | Status | Execution Details |
|---|---|---|---|
| `test_registration_login_profile_and_logout` | Authentication, JWT, Argon2, Logout Revocation | PASS | Verified 201 Created, duplicate email 409 rejection, 401 invalid credentials, 200 login token generation, authenticated profile retrieval, password update and re-hash, 204 logout, and post-logout token rejection (401). |
| `test_satellite_simulation_connection_and_ownership` | Orbital Simulation, Connections, Measurements, Ownership isolation | PASS | Verified satellite catalog listing, visibility calculation from coordinates, simulation run persistence, connection session initiation, signal measurement generation, session termination, and strict tenant isolation (user A cannot view or end user B's resources). |
| `test_admin_route_requires_admin_role` | RBAC Security | PASS | Verified that regular accounts attempting to access `/admin/dashboard` receive `403 Forbidden`. |
| `test_ground_stations_listing` | Ground Station Inventory | PASS | Verified that authenticated users can list ground station records with correct pagination envelope. |
| `test_database_relationships` | SQLAlchemy ORM Integrity | PASS | Verified user-to-simulation cascading relationships and role linkages. |
| `test_passes_telemetry_and_simulation_reports` | Telemetry & Simulation Reports | PASS | Verified real-time telemetry extraction (`orbital_velocity_km_s > 5.0`, sub-satellite coordinates), 12h pass prediction generation, simulation report generation with 3GPP NTN link budget, and CSV data export. |
| `test_solve_kepler_and_true_anomaly` | Celestial Mechanics | PASS | Verified Newton-Raphson Kepler equation convergence to $10^{-9}$ for circular ($e=0$) and eccentric ($e=0.2$) orbits. |
| `test_j2_secular_drift` | Orbital Perturbation | PASS | Verified $J_2$ Earth oblateness secular nodal regression rate ($\approx -5.2^\circ$/day for 53° LEO). |
| `test_wgs84_geodetic_ecef_roundtrip` | Geodetic Coordinates | PASS | Verified sub-millimeter WGS-84 ellipsoid round-trip conversions across Bangalore, San Francisco, equator, and North/South poles using Bowring's method. |
| `test_doppler_shift_and_fspl` | RF Propagation | PASS | Verified Friis FSPL at 2.0 GHz ($158.47\text{ dB}$ at $1000\text{ km}$) and relative velocity Doppler frequency shift ($+33.3\text{ kHz}$ at $-5\text{ km/s}$). |
| `test_apparent_elevation_refraction` | Atmospheric Modeling | PASS | Verified Saastamoinen / Bennett tropospheric refraction model for apparent elevation at horizon. |
| `test_predict_passes_for_constellation` | Visibility Estimation | PASS | Verified multi-satellite pass prediction window sequence ($\text{AOS} < \text{TCA} < \text{LOS}$) with positive contact durations and distance estimates. |

### 1.2 Web Frontend Test Suite (Vitest)
Command executed:
```powershell
npm --prefix web test
```
**Results:** **1 passed (100% success rate)**

| Test Name | Suite | Status | Execution Details |
|---|---|---|---|
| `shows sign in and switches to registration` | Authentication Screen | PASS | Verified render of the sign-in form, field presence, mode switching button, full name input toggling, and clean state initialization. |

### 1.3 TypeScript Compilation & Production Build Check
Command executed:
```powershell
npm --prefix web run build
```
**Results:** **Build succeeded in 8.17s**
- TypeScript compiler (`tsc -b`): **0 type errors**
- Vite production bundle: Generated clean minified HTML, CSS, and JS chunks (`dist/index.html`, `dist/assets/*.css`, `dist/assets/*.js`).

### 1.4 Live API and Integration Verification
Commands executed:
- `OPTIONS /api/v1/auth/login` (Origin: `http://localhost:5174`): **HTTP 200 OK**
- `POST /api/v1/auth/login` with demo admin credentials: **HTTP 200 OK (access_token returned)**
- `GET /health`: **HTTP 200 OK (`{"status":"ok","connectivity":"simulation_only"}`)**
- Vite Reverse Proxy (`http://localhost:5174/api/v1/...`): **HTTP 200 OK**
- Direct API (`http://localhost:8000/api/v1/...`): **HTTP 200 OK**

---

## 2. Environments Not Executed / Blocked

| Component | Target Command | Reason for Non-Execution | Mitigation |
|---|---|---|---|
| Flutter Mobile Client | `flutter analyze`, `flutter test` | The `flutter` SDK and Dart runtime are not installed or configured in the system PATH on this Windows host. | Performed complete static code analysis and syntax auditing of `mobile/lib/main.dart` and `mobile/test/widget_test.dart`. Fixed runtime type cast bugs in error parsing and connection requests. Full instructions provided for executing on developer machines with Flutter installed. |

