# SkyLink Direct — Internet Connectivity Architecture

## 1. Executive Summary & Objective

**SkyLink Direct** is designed to model and prototype direct mobile-to-satellite internet connectivity. This document details the hybrid architecture implemented in the current prototype, clearly delineating between simulated orbital link modeling and live terrestrial IP transit, and providing a rigorous roadmap toward physical 3GPP Rel-17 Non-Terrestrial Network (NTN) integration.

```
+-------------------------------------------------------------------------------------------------------------+
|                                    HYBRID CONNECTIVITY ARCHITECTURE                                         |
+-------------------------------------------------------------------------------------------------------------+
|                                                                                                             |
|  [ Mobile Terminal / Web Client ]                                                                           |
|         │                                                                                                   |
|         ├──────────────────────────────────────────┐                                                        |
|         ▼                                          ▼                                                        |
|  [ Terrestrial IP Layer ]                [ 3GPP Rel-17 NTN Simulation Engine ]                              |
|   • HTTP / TCP Live Socket Layer          • WGS-84 Geodetic / ECEF Reference Model                          |
|   • Live Latency / RTT Probing            • S-Band (2.0 GHz) Service Link Budget                            |
|   • Controlled Download Streaming         • Free Space Path Loss + ITU-R P.676 Atmospheric                  |
|   • Controlled Binary Upload Benchmark    • Keplerian True Anomaly + J2 Nodal Precession                    |
|   • Fast Ethernet / 4G / 5G / Wi-Fi       • Doppler Shift (\Delta f) Tracking                               |
|         │                                          │                                                        |
|         └────────────────────┬─────────────────────┘                                                        |
|                              ▼                                                                              |
|               [ SkyLink Direct FastAPI Backend ]                                                            |
|               • Network Ping & Telemetry Service                                                            |
|               • Speed Test Data Stream Engines                                                              |
|               • Satellite-Gateway Feeder Link Associator                                                    |
|               • Direct-to-Device Dashboard Aggregator                                                       |
|                              │                                                                              |
|                              ▼                                                                              |
|               [ Teleport Feeder Gateways (Ka-Band) ] ──▶ [ Public Internet Backbone / UPF Core ]            |
+-------------------------------------------------------------------------------------------------------------+
```

---

## 2. Current Implementation vs. Operational Reality

| Component | Current Prototype Implementation | Operational Physical Reality (Future) |
|---|---|---|
| **Mobile Access** | Wi-Fi / LTE / Localhost simulated fallback over standard HTTP/REST sockets. | 3GPP Rel-17/18 NTN user equipment with specialized RF baseband chips (e.g. MediaTek MT6825 / Qualcomm Snapdragon Satellite). |
| **Space Segment** | Keplerian orbit propagator with J2 earth oblateness perturbation modeling 18 LEO satellites. | Constellation of LEO satellites with active phased-array beamforming antennas and regenerative/transparent transponders. |
| **Service Link (User-to-Sat)** | Mathematical link budget (S-Band 2.0 GHz), Saastamoinen tropospheric refraction, and FSPL computation. | Real RF transmission in MSS (Mobile Satellite Service) bands (1.6/2.4 GHz or 2.0/2.2 GHz) with circular polarization. |
| **Feeder Link (Sat-to-Gateway)** | High-capacity Ka-band (28.5–29.0 GHz) modeled routing with dedicated ground teleport records. | Real Ka/Q/V-band tracking parabolic dish ground teleports with high-speed optical fiber interconnects. |
| **Throughput Measurement** | Synthetic payload streaming (up to 10 MB download / 512 KB upload chunks) measuring real system I/O. | Real RF bandwidth sharing (5–20 MHz channels) dynamically constrained by rain fade and satellite elevation. |

> [!IMPORTANT]
> **Prototype Simulation Disclaimer:**
> SkyLink Direct currently models RF propagation, orbital mechanics, Doppler shifts, and gateway routing mathematically while executing live network performance benchmarks over terrestrial sockets. It does not emit live RF signals to physical satellites without dedicated orbital transceiver hardware.

---

## 3. Core System Components

### 3.1 Mobile Client Layer (Flutter Android/iOS)
- **Status Monitor:** Live connectivity polling via `Api.ping()` with automatic reconnection logic.
- **Speed Test Engine:** Streams controlled binary data chunks from `/api/v1/network/speedtest/download` and pushes controlled binary blocks to `/api/v1/network/speedtest/upload`.
- **D2D Dashboard:** Visualizes terminal coordinates, active link mode, 5-step routing path, satellite visibility, and teleport status.

### 3.2 Web Application Layer (React + TypeScript)
- **Direct-to-Device Dashboard (`D2DDashboard.tsx`):**
  - Renders 5-node routing flow: `Mobile UE -> Satellite Radio Access -> Satellite Node -> Feeder Gateway -> Internet`.
  - Live benchmark execution with instantaneous latency, download, upload, and RF signal level cards.
  - Interactive city presets (Bangalore, London, SF, Tokyo, Sydney) and browser GPS geolocation.
  - Historical test logs and gateway inventory tables.
- **Satellite Gateway Administration (`AdminModule.tsx`):**
  - Add, edit, inspect, and delete Ka-band feeder gateway teleports.
  - Configure uplink/downlink capacities, feeder frequencies, egress IP addresses, and linked satellite constellations.

### 3.3 Backend Layer (FastAPI + SQLAlchemy)
- **Modular APIs:**
  - `/api/v1/network/ping`: Measures millisecond server latency and client IP.
  - `/api/v1/network/speedtest/download`: High-performance streaming response with synthetic binary byte blocks.
  - `/api/v1/network/speedtest/upload`: Streams incoming byte arrays, computing throughput in Mbps.
  - `/api/v1/network/tests`: Stores and retrieves benchmark history with user audit association.
  - `/api/v1/network/d2d-dashboard`: Aggregates mobile status, visible satellites, RF link estimates, feeder gateway teleports, and 5-step routing paths.
  - `/api/v1/gateways`: Full CRUD management for satellite teleport stations and constellation feeder associations.

---

## 4. Evolution Steps to Real Satellite Service

1. **Phase A (Current):** Prototype simulation with Keplerian orbit propagation, link budget formulas, and terrestrial benchmark testbeds.
2. **Phase B (Hardware-in-the-Loop):** Connect Software Defined Radios (SDR, e.g., USRP B210 / HackRF) running open-source 3GPP NTN stacks (srsRAN Project) to transmit actual Rel-17 waveforms over RF test benches.
3. **Phase C (LEO CubeSat Demonstration):** Partner with orbital satellite operators or launch a 3U/6U CubeSat carrying an S-band SDR transponder and Ka-band feeder downlink.
4. **Phase D (Commercial Constellation Transit):** Route live user internet data through orbital transponders and terrestrial teleports directly to standard smartphones.

