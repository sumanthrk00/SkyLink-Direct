-- PostgreSQL reference schema matching backend/app/models/models.py.
CREATE TABLE roles (id SERIAL PRIMARY KEY, name VARCHAR(30) NOT NULL UNIQUE);
CREATE TABLE users (
  id UUID PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL, role_id INTEGER NOT NULL REFERENCES roles(id),
  is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_users_email ON users(email);
CREATE TABLE devices (
  id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL, platform VARCHAR(30) NOT NULL DEFAULT 'web',
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_devices_user_id ON devices(user_id);
CREATE TABLE satellites (
  id UUID PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, orbit_type VARCHAR(30) NOT NULL DEFAULT 'LEO',
  altitude_km DOUBLE PRECISION NOT NULL DEFAULT 550, status VARCHAR(30) NOT NULL DEFAULT 'active',
  inclination_deg DOUBLE PRECISION NOT NULL DEFAULT 53, raan_deg DOUBLE PRECISION NOT NULL DEFAULT 0,
  phase_deg DOUBLE PRECISION NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE ground_stations (
  id UUID PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, latitude_deg DOUBLE PRECISION NOT NULL,
  longitude_deg DOUBLE PRECISION NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'demo',
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE simulation_runs (
  id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  satellite_id UUID REFERENCES satellites(id), status VARCHAR(30) NOT NULL DEFAULT 'completed',
  latitude_deg DOUBLE PRECISION NOT NULL, longitude_deg DOUBLE PRECISION NOT NULL,
  elevation_deg DOUBLE PRECISION NOT NULL, distance_km DOUBLE PRECISION NOT NULL,
  signal_strength DOUBLE PRECISION NOT NULL, latency_ms DOUBLE PRECISION NOT NULL,
  packet_loss DOUBLE PRECISION NOT NULL, download_mbps DOUBLE PRECISION NOT NULL,
  upload_mbps DOUBLE PRECISION NOT NULL, created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_simulation_runs_user_created ON simulation_runs(user_id, created_at);
CREATE TABLE connection_sessions (
  id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  satellite_id UUID REFERENCES satellites(id), status VARCHAR(30) NOT NULL DEFAULT 'connected',
  started_at TIMESTAMPTZ NOT NULL, ended_at TIMESTAMPTZ
);
CREATE INDEX ix_connection_sessions_user_status ON connection_sessions(user_id, status);
CREATE TABLE signal_measurements (
  id UUID PRIMARY KEY, session_id UUID NOT NULL REFERENCES connection_sessions(id) ON DELETE CASCADE,
  signal_strength DOUBLE PRECISION NOT NULL, latency_ms DOUBLE PRECISION NOT NULL,
  packet_loss DOUBLE PRECISION NOT NULL, measured_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_signal_measurements_measured_at ON signal_measurements(measured_at);
CREATE TABLE network_events (
  id UUID PRIMARY KEY, user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type VARCHAR(50) NOT NULL, description TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE notifications (
  id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(120) NOT NULL, body TEXT NOT NULL, is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE revoked_tokens (jti VARCHAR(36) PRIMARY KEY, expires_at TIMESTAMPTZ NOT NULL);
