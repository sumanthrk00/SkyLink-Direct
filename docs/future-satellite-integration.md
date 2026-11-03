# Future Satellite Integration Architecture (3GPP Rel-17 NTN)

## 1. Roadmap to Physical Space Segment Integration

SkyLink Direct's architectural design provides a clear path from mathematical and terrestrial simulation to physical Direct-to-Device (D2D) satellite communication.

```
+------------------------------------------------------------------------------------------------+
|                             D2D INTEGRATION MATURITY ROADMAP                                   |
+------------------------------------------------------------------------------------------------+
|                                                                                                |
|   LEVEL 1: Mathematical Prototype (Current)                                                    |
|   • Keplerian J2 nodal orbit propagation                                                       |
|   • ITU-R P.676 & Free Space Path Loss modeling                                                |
|   • Controlled terrestrial streaming benchmarks                                                |
|                                                                                                |
|   LEVEL 2: Software-Defined Radio (SDR) Testbed                                                |
|   • USRP B210 / HackRF One hardware integration                                                |
|   • srsRAN 3GPP Rel-17 NTN gNodeB software stack                                               |
|   • S-Band (2.0 GHz) RF channel emulation (multipath fading + Doppler simulation)              |
|                                                                                                |
|   LEVEL 3: Physical Transceiver User Terminal                                                  |
|   • Integration with 3GPP NTN commercial baseband modules (MediaTek MT6825 / Qualcomm X75)   |
|   • Narrowband IoT (NB-IoT NTN) two-way messaging & telemetry packets                          |
|   • Circular polarization patch antennas with hemispherical gain patterns                      |
|                                                                                                |
|   LEVEL 4: Orbital Spacecraft Demonstration                                                    |
|   • Launch of 3U/6U CubeSat carrying regenerative SDR transponder payload                      |
|   • Ka-band feeder link downlink to certified teleport stations                                |
|   • Live IP packet routing through 5G User Plane Function (UPF) core network                   |
+------------------------------------------------------------------------------------------------+
```

---

## 2. 3GPP Rel-17 & Rel-18 NTN Specifications

### 2.1 Band Allocations for Direct-to-Device
Standard commercial smartphones cannot receive high-frequency Ku/Ka-band without bulky satellite dish antennas. Direct-to-Device utilizes standard Mobile Satellite Service (MSS) sub-3 GHz frequencies:

| 3GPP Band | Frequency (Uplink / Downlink) | Polarization | Mode | Use Case |
|---|---|---|---|---|
| **Band n255** | UL: 1626.5–1660.5 MHz / DL: 1525–1559 MHz (L-Band) | RHCP | FDD | IoT & Messaging |
| **Band n256** | UL: 1980–2010 MHz / DL: 2170–2200 MHz (S-Band) | RHCP | FDD | Broadband Voice & Data |

### 2.2 Timing Advance (TA) and Doppler Compensation
Because LEO satellites move across the sky at $\sim 7.6\text{ km/s}$, high Doppler shifts ($\Delta f \approx \pm 35\text{ kHz}$ at 2.0 GHz) and large round-trip propagation delays ($\tau \approx 10 - 25\text{ ms}$) violate standard terrestrial cellular timeouts.

1. **Pre-compensation at User Equipment (UE):**
   - The device reads its current GPS location and downloads the satellite's orbital ephemeris.
   - The UE pre-shifts its carrier frequency by $-\Delta f_{\text{doppler}}$ before transmitting uplink bursts.
   - The UE applies a Common Timing Advance ($T_{\text{common}}$) calculated from the satellite to reference cell center.
2. **Post-compensation at Spacecraft / Gateway:**
   - Residual Doppler is removed by phase-locked loops (PLL) on the satellite transponder or feeder gateway receiver.

---

## 3. Real-Time Ephemeris Ingest Architecture

Currently, SkyLink Direct models 18 reference LEO satellites using Keplerian orbital elements with J2 secular nodal drift. To integrate real satellites (e.g. Starlink, AST SpaceMobile, Lynk Global, Iridium-NEXT):

```mermaid
flowchart LR
    A["CelesTrak / Space-Track API"] -->|"REST / JSON"| B["SkyLink Ephemeris Ingest Worker"]
    B -->|"SGP4 Orbit Propagator"| C["Real-Time State Vector (X, Y, Z, Vx, Vy, Vz)"]
    C -->|"PostgreSQL / SQLite"| D["Satellites Table"]
    D -->|"FastAPI Engine"| E["Direct-to-Device Dashboard & Pass Prediction"]
```

1. **Scheduled Ingest Worker:** Runs an automated cron task querying NORAD Two-Line Element (TLE) sets or OMM (Orbit Mean-Elements Messages).
2. **SGP4 Propagator:** High-precision Simplified General Perturbations-4 algorithm replaces pure Keplerian two-body calculations to account for atmospheric drag and third-body lunar/solar gravitational perturbations.

---

## 4. Hardware Architecture: Regenerative vs. Transparent Payloads

```
BENT-PIPE (TRANSPARENT) TRANSPONDER
[ Mobile UE ] ──(S-Band)──▶ [ Spacecraft RF Repeater / Filter ] ──(Ka-Band)──▶ [ Gateway Teleport ] ──▶ [ Core Network ]
(Low satellite complexity, high gateway reliance)

REGENERATIVE PAYLOAD (ON-BOARD gNodeB)
[ Mobile UE ] ──(S-Band)──▶ [ Spacecraft On-Board Baseband / UPF ] ──(Inter-Satellite Link)──▶ [ Global Mesh ]
(Direct satellite-to-satellite routing, low terrestrial dependence)
```

SkyLink Direct's database schema and API routing models both paradigms:
- The `SatelliteGateway` association represents transparent feeder backhaul.
- The `simulated_routing_path` records in `network.py` support modular payload state classification (`regenerative` vs `transparent`).

