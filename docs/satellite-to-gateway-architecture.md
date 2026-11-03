# Satellite-to-Gateway Architecture & Feeder Links

## 1. High-Level Architecture

In modern Non-Terrestrial Networks (NTN), communications are bifurcated into two distinct radio frequency link segments:

1. **Service Link (Direct-to-Device / Mobile Access Link):**
   - Operating between the **User Equipment (UE)** and the **Satellite Payload**.
   - Frequency: S-Band ($2.0\text{ GHz} - 2.2\text{ GHz}$) or L-Band ($1.5\text{ GHz} - 1.6\text{ GHz}$).
   - Standard: 3GPP Rel-17/18 NR-NTN or NB-IoT-NTN.
   - Purpose: Direct connection to standard smartphones and portable terminals.

2. **Feeder Link (Gateway Backhaul Trunk):**
   - Operating between the **Satellite Node** and the **Earth Teleport Gateway**.
   - Frequency: Ka-Band ($28.5\text{ GHz} - 29.5\text{ GHz}$ uplink, $18.5\text{ GHz} - 19.5\text{ GHz}$ downlink).
   - High-throughput multi-carrier QAM modulation with wide bandwidth channels ($500\text{ MHz} - 1\text{ GHz}$).
   - Purpose: Aggregate internet transit backhaul into terrestrial Core Network Packet Gateways (P-GW / UPF).

```
                      +-----------------------------+
                      |   Satellite Constellation   |
                      |       (Demo LEO 01-18)      |
                      +-----------------------------+
                               /            \
                              /              \
             Service Link    /                \   Feeder Link
            (S-Band 2.0 GHz)/                  \  (Ka-Band 28.5 GHz)
                           /                    \
                          v                      v
             +-----------------------+   +------------------------------+
             | User Terminal (UE)    |   | Earth Teleport Gateway       |
             | • Smartphones         |   | • Bangalore Teleport (India) |
             | • IoT Transceivers    |   | • London Station (UK)        |
             | • Web/Mobile Clients  |   | • California West (USA)      |
             +-----------------------+   +------------------------------+
                                                        │
                                                        ▼ (High-Speed Fiber)
                                         +------------------------------+
                                         | Core Network / 5G UPF        |
                                         | Global Public Internet       |
                                         +------------------------------+
```

---

## 2. Satellite Gateway Database Model (`SatelliteGateway`)

In SkyLink Direct, satellite teleport gateways are modeled as first-class database entities with association mappings to the orbital fleet:

```sql
CREATE TABLE satellite_gateways (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    latitude_deg FLOAT NOT NULL,
    longitude_deg FLOAT NOT NULL,
    elevation_m FLOAT NOT NULL DEFAULT 50.0,
    feeder_frequency_ghz FLOAT NOT NULL DEFAULT 28.5,
    status VARCHAR(30) NOT NULL DEFAULT 'operational',
    ip_address VARCHAR(45) NOT NULL DEFAULT '127.0.0.1',
    uplink_capacity_gbps FLOAT NOT NULL DEFAULT 10.0,
    downlink_capacity_gbps FLOAT NOT NULL DEFAULT 40.0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Many-to-Many Association Table
CREATE TABLE gateway_satellites (
    gateway_id UUID REFERENCES satellite_gateways(id) ON DELETE CASCADE,
    satellite_id UUID REFERENCES satellites(id) ON DELETE CASCADE,
    PRIMARY KEY (gateway_id, satellite_id)
);
```

### Reference Teleports Initialized:
1. **Bangalore Teleport Gateway:**
   - Coordinates: $13.0827^\circ\text{N}, 77.5877^\circ\text{E}$ (Elevation: $920\text{ m}$)
   - Feeder Frequency: $28.5\text{ GHz}$
   - Capacity: $40.0\text{ Gbps}$ Downlink / $10.0\text{ Gbps}$ Uplink
   - Egress IP: `192.168.10.1`
2. **London Teleport Station:**
   - Coordinates: $51.5074^\circ\text{N}, -0.1278^\circ\text{W}$ (Elevation: $35\text{ m}$)
   - Feeder Frequency: $28.5\text{ GHz}$
   - Capacity: $40.0\text{ Gbps}$ Downlink / $10.0\text{ Gbps}$ Uplink
   - Egress IP: `192.168.20.1`
3. **California West Gateway:**
   - Coordinates: $37.7749^\circ\text{N}, -122.4194^\circ\text{W}$ (Elevation: $15\text{ m}$)
   - Feeder Frequency: $29.0\text{ GHz}$
   - Capacity: $50.0\text{ Gbps}$ Downlink / $12.5\text{ Gbps}$ Uplink
   - Egress IP: `192.168.30.1`

---

## 3. Telemetry, Tracking & Gateway Handover Dynamics

### 3.1 Slant Distance & Minimum Elevation Constraint
A teleport gateway establishes a feeder link with an overhead satellite when the apparent elevation angle exceeds the gateway mask angle $\theta_{\text{min}} = 10^\circ$:

$$\theta_{\text{elev}} = \arcsin\left(\frac{R_E + h}{d}\sin(\psi) - \frac{R_E}{d}\right) \ge 10.0^\circ$$

Where:
- $R_E = 6378.137\text{ km}$ (Earth radius)
- $h$ is orbital altitude (550 km)
- $d$ is slant distance between gateway and satellite
- $\psi$ is earth central angle

### 3.2 Gateway Handover Strategy
As a LEO spacecraft moves along its ground track at orbital velocity $v_{\text{orb}} \approx 7.6\text{ km/s}$, its feeder link pass duration over a given gateway lasts approximately $6 - 10\text{ minutes}$.

- **Make-Before-Break (MBB) Handover:**
  Prior to Loss of Signal (LOS) at the departing teleport, the spacecraft activates a secondary feeder beam toward an approaching teleport or switches to an alternate satellite within visibility of the same teleport.
- **Dynamic Capacity Routing:**
  The FastAPI endpoint `GET /api/v1/network/d2d-dashboard` identifies the nearest operational gateway to the user's location and calculates feeder route distance and latency.

