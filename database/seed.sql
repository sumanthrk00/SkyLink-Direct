-- Optional PostgreSQL reference seed. Application startup performs equivalent idempotent seeding.
INSERT INTO roles(name) VALUES ('user'), ('admin') ON CONFLICT (name) DO NOTHING;
INSERT INTO satellites(id, name, orbit_type, altitude_km, status, inclination_deg, raan_deg, phase_deg, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'Demo LEO 01', 'LEO', 550, 'active', 53, 0, 0, now(), now()),
  (gen_random_uuid(), 'Demo LEO 02', 'LEO', 550, 'active', 53, 120, 120, now(), now()),
  (gen_random_uuid(), 'Demo LEO 03', 'LEO', 1200, 'active', 70, 240, 240, now(), now())
ON CONFLICT (name) DO NOTHING;
INSERT INTO ground_stations(id, name, latitude_deg, longitude_deg, status, created_at, updated_at)
VALUES(gen_random_uuid(), 'Demo Ground Station', 12.9716, 77.5946, 'demo', now(), now())
ON CONFLICT (name) DO NOTHING;
