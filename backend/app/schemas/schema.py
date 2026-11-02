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
