# Database ER diagram

```mermaid
erDiagram
  ROLES ||--o{ USERS : assigns
  USERS ||--o{ DEVICES : owns
  USERS ||--o{ SIMULATION_RUNS : creates
  SATELLITES o|--o{ SIMULATION_RUNS : selected_for
  USERS ||--o{ CONNECTION_SESSIONS : starts
  SATELLITES o|--o{ CONNECTION_SESSIONS : uses
  CONNECTION_SESSIONS ||--o{ SIGNAL_MEASUREMENTS : records
  USERS o|--o{ NETWORK_EVENTS : triggers
  USERS ||--o{ NOTIFICATIONS : receives
  USERS o|--o{ AUDIT_LOGS : performs
  USERS o|--o{ CONNECTIVITY_TESTS : executes
  SATELLITE_GATEWAYS ||--o{ GATEWAY_SATELLITES : links
  SATELLITES ||--o{ GATEWAY_SATELLITES : supported_by
  USERS {
    uuid id PK
    string name
    string email UK
    string password_hash
    int role_id FK
    bool is_active
    datetime created_at
    datetime updated_at
  }
  ROLES { int id PK string name UK }
  DEVICES { uuid id PK uuid user_id FK string name string platform }
  SATELLITES { uuid id PK string name UK string orbit_type float altitude_km float inclination_deg float raan_deg float phase_deg string status }
  GROUND_STATIONS { uuid id PK string name UK float latitude_deg float longitude_deg string status }
  SATELLITE_GATEWAYS { uuid id PK string name UK float latitude_deg float longitude_deg float elevation_m float feeder_frequency_ghz string status string ip_address float uplink_capacity_gbps float downlink_capacity_gbps datetime created_at }
  GATEWAY_SATELLITES { uuid gateway_id PK_FK uuid satellite_id PK_FK }
  CONNECTIVITY_TESTS { uuid id PK uuid user_id FK string client_platform float ping_latency_ms float download_speed_mbps float upload_speed_mbps float packet_loss_percent string test_type string status string server_location datetime created_at }
  SIMULATION_RUNS { uuid id PK uuid user_id FK uuid satellite_id FK string status float latitude_deg float longitude_deg }
  CONNECTION_SESSIONS { uuid id PK uuid user_id FK uuid satellite_id FK string status datetime started_at datetime ended_at }
  SIGNAL_MEASUREMENTS { uuid id PK uuid session_id FK float signal_strength float latency_ms float packet_loss datetime measured_at }
  NETWORK_EVENTS { uuid id PK uuid user_id FK string event_type string description datetime created_at }
  NOTIFICATIONS { uuid id PK uuid user_id FK string title string body bool is_read datetime created_at }
  REVOKED_TOKENS { string jti PK datetime expires_at }
  AUDIT_LOGS { uuid id PK uuid admin_id FK string admin_email string action string target_type string target_id string details datetime created_at }
```

UUID primary keys are used for user-owned, operational, and administrative records. Emails and named reference entities are unique. Foreign keys enforce relationships; indexes cover user email, user simulation history, user session status, device owner, measurement time, gateway feeder frequencies, connectivity test platform, and audit log creation time. Revoked JWT identifiers are stored until token expiry so logout can invalidate access.

Ground stations and satellite gateways are managed via dedicated endpoints (`/api/v1/ground-stations`, `/api/v1/admin/ground-stations`, and `/api/v1/gateways`); administrative actions automatically populate `AUDIT_LOGS` with target entity references and before/after mutation details.

### Newly Added Models (Phases 1 & 2):
1. **`SATELLITE_GATEWAYS`:**
   - Dedicated table for Earth teleport stations providing Ka-band (28.5–29.0 GHz) high-speed feeder links.
   - Stores geographic location (lat/lon/elevation), public egress IP, and uplink/downlink capacities in Gbps.
2. **`GATEWAY_SATELLITES`:**
   - Association table representing many-to-many feeder link connections between orbital satellites and ground teleports.
3. **`CONNECTIVITY_TESTS`:**
   - Records client internet performance benchmarks across mobile and web platforms (ping latency, download Mbps, upload Mbps, packet loss, server teleport location).
4. **`AUDIT_LOGS`:**
   - Tracks administrative actions and gateway modifications with timestamp, admin email, action type, and JSON details.
