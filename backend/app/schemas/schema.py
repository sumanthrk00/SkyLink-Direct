from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    role: str
    created_at: datetime


class SatelliteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    orbit_type: str
    altitude_km: float
    status: str
    inclination_deg: float


class GroundStationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    latitude_deg: float
    longitude_deg: float
    status: str


class GroundStationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)
    status: str = Field(default="demo", max_length=30)


class SimulationRequest(BaseModel):
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)


class SimulationResponse(BaseModel):
    id: UUID
    status: str
    latitude_deg: float
    longitude_deg: float
    satellite_id: UUID | None
    satellite_name: str | None
    elevation_deg: float
    distance_km: float
    signal_strength: float
    latency_ms: float
    packet_loss: float
    download_mbps: float
    upload_mbps: float
    result_type: str = "illustrative_estimate"
    created_at: datetime


class ConnectionCreateRequest(BaseModel):
    simulation_id: UUID | None = None
    latitude_deg: float | None = Field(default=None, ge=-90, le=90)
    longitude_deg: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def require_location_or_simulation(self) -> "ConnectionCreateRequest":
        if self.simulation_id is None and (self.latitude_deg is None or self.longitude_deg is None):
            raise ValueError("Provide a simulation_id or both latitude_deg and longitude_deg")
        if (self.latitude_deg is None) != (self.longitude_deg is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


class ConnectionResponse(BaseModel):
    id: UUID
    satellite_id: UUID | None
    satellite_name: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None


class PassPredictionItem(BaseModel):
    satellite_id: str
    satellite_name: str
    aos_utc: datetime
    tca_utc: datetime
    los_utc: datetime
    max_elevation_deg: float
    duration_seconds: int
    tca_distance_km: float
    tca_azimuth_deg: float


class PassPredictionResponse(BaseModel):
    observer_latitude_deg: float
    observer_longitude_deg: float
    start_utc: datetime
    duration_hours: float
    min_elevation_deg: float
    total_passes: int
    passes: list[PassPredictionItem]


class SatelliteTelemetryResponse(BaseModel):
    satellite_id: UUID
    name: str
    orbit_type: str
    altitude_km: float
    timestamp_utc: datetime
    subsatellite_latitude_deg: float
    subsatellite_longitude_deg: float
    orbital_velocity_km_s: float
    orbital_period_minutes: float
    ecef_coordinates_km: dict[str, float]


class SimulationReportResponse(BaseModel):
    simulation_id: UUID
    created_at: datetime
    observer_location: dict[str, float]
    satellite: dict[str, str | float] | None
    rf_link_budget: dict[str, float | str]
    throughput_capacity: dict[str, float]
    channel_status: str
    prototype_disclaimer: str


class PageResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int


class AdminUserListItem(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    simulations_count: int = 0
    connections_count: int = 0


class AdminUserUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    name: str | None = None


class SatelliteCreateAdminRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    orbit_type: str = Field(default="LEO", max_length=30)
    altitude_km: float = Field(ge=100, le=40000)
    inclination_deg: float = Field(ge=0, le=180)
    raan_deg: float = Field(default=0.0, ge=0, le=360)
    phase_deg: float = Field(default=0.0, ge=0, le=360)
    status: str = Field(default="active", max_length=30)


class SatelliteUpdateAdminRequest(BaseModel):
    name: str | None = None
    altitude_km: float | None = None
    inclination_deg: float | None = None
    raan_deg: float | None = None
    phase_deg: float | None = None
    status: str | None = None


class GroundStationUpdateAdminRequest(BaseModel):
    name: str | None = None
    latitude_deg: float | None = Field(default=None, ge=-90, le=90)
    longitude_deg: float | None = Field(default=None, ge=-180, le=180)
    status: str | None = None


class AdminSimulationItem(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    satellite_name: str | None
    status: str
    latitude_deg: float
    longitude_deg: float
    elevation_deg: float
    distance_km: float
    signal_strength: float
    latency_ms: float
    packet_loss: float
    download_mbps: float
    upload_mbps: float
    created_at: datetime


class AdminSessionItem(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    satellite_name: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    signal_strength: float | None = None
    latency_ms: float | None = None
    packet_loss: float | None = None


class AuditLogResponse(BaseModel):
    id: UUID
    admin_id: UUID | None
    admin_email: str
    action: str
    target_type: str
    target_id: str | None
    details: str
    created_at: datetime


class AdminSystemHealthResponse(BaseModel):
    api_status: str
    connectivity_mode: str
    database_engine: str
    database_connected: bool
    table_counts: dict[str, int]
    simulation_engine: dict[str, str]
    system_uptime_seconds: float
    server_time_utc: datetime


class PingResponse(BaseModel):
    status: str = "online"
    client_ip: str
    server_time_utc: datetime
    timestamp_ms: float


class ConnectivityTestCreateRequest(BaseModel):
    client_platform: str = Field(default="mobile_android", max_length=30)
    ping_latency_ms: float = Field(ge=0.0)
    download_speed_mbps: float = Field(ge=0.0)
    upload_speed_mbps: float = Field(ge=0.0)
    packet_loss_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    test_type: str = Field(default="internet_speedtest", max_length=30)
    status: str = Field(default="completed", max_length=30)
    server_location: str = Field(default="Local Gateway", max_length=100)


class ConnectivityTestResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    client_platform: str
    ping_latency_ms: float
    download_speed_mbps: float
    upload_speed_mbps: float
    packet_loss_percent: float
    test_type: str
    status: str
    server_location: str
    created_at: datetime


class UploadTestResponse(BaseModel):
    bytes_received: int
    duration_ms: float
    upload_speed_mbps: float
    timestamp: datetime


class GatewayCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(ge=-180.0, le=180.0)
    elevation_m: float = Field(default=50.0, ge=-500.0, le=9000.0)
    feeder_frequency_ghz: float = Field(default=28.5, ge=1.0, le=100.0)
    status: str = Field(default="operational", max_length=30)
    ip_address: str = Field(default="127.0.0.1", max_length=45)
    uplink_capacity_gbps: float = Field(default=10.0, ge=0.1)
    downlink_capacity_gbps: float = Field(default=40.0, ge=0.1)
    satellite_ids: list[UUID] = []


class GatewayUpdateRequest(BaseModel):
    name: str | None = None
    latitude_deg: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude_deg: float | None = Field(default=None, ge=-180.0, le=180.0)
    elevation_m: float | None = None
    feeder_frequency_ghz: float | None = None
    status: str | None = None
    ip_address: str | None = None
    uplink_capacity_gbps: float | None = None
    downlink_capacity_gbps: float | None = None
    satellite_ids: list[UUID] | None = None


class GatewayResponse(BaseModel):
    id: UUID
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    feeder_frequency_ghz: float
    status: str
    ip_address: str
    uplink_capacity_gbps: float
    downlink_capacity_gbps: float
    supported_satellites_count: int
    supported_satellites: list[str]
    created_at: datetime


class DirectToDeviceDashboardResponse(BaseModel):
    mobile_device_status: dict
    internet_availability: dict
    selected_satellite: dict | None
    satellite_visibility: dict | None
    gateway_status: dict | None
    simulated_routing_path: list[dict]
    metrics: dict
    last_connectivity_test: dict | None
    prototype_disclaimer: str
