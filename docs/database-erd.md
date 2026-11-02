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
  SATELLITES { uuid id PK string name UK string orbit_type float altitude_km string status }
  GROUND_STATIONS { uuid id PK string name UK float latitude_deg float longitude_deg }
  SIMULATION_RUNS { uuid id PK uuid user_id FK uuid satellite_id FK string status float latitude_deg float longitude_deg }
  CONNECTION_SESSIONS { uuid id PK uuid user_id FK uuid satellite_id FK string status datetime started_at datetime ended_at }
  SIGNAL_MEASUREMENTS { uuid id PK uuid session_id FK float signal_strength float latency_ms float packet_loss datetime measured_at }
  NETWORK_EVENTS { uuid id PK uuid user_id FK string event_type string description datetime created_at }
  NOTIFICATIONS { uuid id PK uuid user_id FK string title string body bool is_read datetime created_at }
  REVOKED_TOKENS { string jti PK datetime expires_at }
```

UUID primary keys are used for user-owned and operational records. Emails and named reference entities are unique. Foreign keys enforce relationships; indexes cover user email, user simulation history, user session status, device owner and measurement time. Revoked JWT identifiers are stored until token expiry so logout can invalidate access.

Ground stations are managed via dedicated endpoints (`/api/v1/ground-stations`); notifications are modeled for downstream alert propagation.
