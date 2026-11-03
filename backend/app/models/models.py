import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[Role] = relationship(back_populates="users")
    devices: Mapped[list["Device"]] = relationship(back_populates="user")
    simulations: Mapped[list["SimulationRun"]] = relationship(back_populates="user")
    connections: Mapped[list["ConnectionSession"]] = relationship(back_populates="user")
    connectivity_tests: Mapped[list["ConnectivityTest"]] = relationship(back_populates="user")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="web")
    user: Mapped[User] = relationship(back_populates="devices")


class Satellite(TimestampMixin, Base):
    __tablename__ = "satellites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    orbit_type: Mapped[str] = mapped_column(String(30), nullable=False, default="LEO")
    altitude_km: Mapped[float] = mapped_column(Float, nullable=False, default=550.0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    inclination_deg: Mapped[float] = mapped_column(Float, nullable=False, default=53.0)
    raan_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    phase_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    simulations: Mapped[list["SimulationRun"]] = relationship(back_populates="satellite")
    connections: Mapped[list["ConnectionSession"]] = relationship(back_populates="satellite")
    gateways: Mapped[list["SatelliteGateway"]] = relationship(secondary="gateway_satellites", back_populates="satellites")



gateway_satellites = Table(
    "gateway_satellites",
    Base.metadata,
    Column("gateway_id", Uuid(as_uuid=True), ForeignKey("satellite_gateways.id", ondelete="CASCADE"), primary_key=True),
    Column("satellite_id", Uuid(as_uuid=True), ForeignKey("satellites.id", ondelete="CASCADE"), primary_key=True),
)


class SatelliteGateway(TimestampMixin, Base):
    __tablename__ = "satellite_gateways"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    latitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    longitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    feeder_frequency_ghz: Mapped[float] = mapped_column(Float, nullable=False, default=28.5)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="operational")
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, default="127.0.0.1")
    uplink_capacity_gbps: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    downlink_capacity_gbps: Mapped[float] = mapped_column(Float, nullable=False, default=40.0)
    satellites: Mapped[list["Satellite"]] = relationship(secondary="gateway_satellites", back_populates="gateways")


class ConnectivityTest(Base):
    __tablename__ = "connectivity_tests"
    __table_args__ = (Index("ix_connectivity_tests_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    client_platform: Mapped[str] = mapped_column(String(30), nullable=False, default="mobile_android")
    ping_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    download_speed_mbps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    upload_speed_mbps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    packet_loss_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    test_type: Mapped[str] = mapped_column(String(30), nullable=False, default="internet_speedtest")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    server_location: Mapped[str] = mapped_column(String(100), nullable=False, default="Local Gateway")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    user: Mapped["User"] = relationship(back_populates="connectivity_tests")


class GroundStation(TimestampMixin, Base):
    __tablename__ = "ground_stations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    latitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    longitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="demo")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (Index("ix_simulation_runs_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    satellite_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("satellites.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    latitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    longitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_deg: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    packet_loss: Mapped[float] = mapped_column(Float, nullable=False)
    download_mbps: Mapped[float] = mapped_column(Float, nullable=False)
    upload_mbps: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    user: Mapped[User] = relationship(back_populates="simulations")
    satellite: Mapped[Satellite | None] = relationship(back_populates="simulations")


class ConnectionSession(Base):
    __tablename__ = "connection_sessions"
    __table_args__ = (Index("ix_connection_sessions_user_status", "user_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    satellite_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("satellites.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="connected")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="connections")
    satellite: Mapped[Satellite | None] = relationship(back_populates="connections")
    measurements: Mapped[list["SignalMeasurement"]] = relationship(back_populates="session")


class SignalMeasurement(Base):
    __tablename__ = "signal_measurements"
    __table_args__ = (Index("ix_signal_measurements_measured_at", "measured_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connection_sessions.id", ondelete="CASCADE"), nullable=False
    )
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    packet_loss: Mapped[float] = mapped_column(Float, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    session: Mapped[ConnectionSession] = relationship(back_populates="measurements")


class NetworkEvent(Base):
    __tablename__ = "network_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


def model_dict(model: Any) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}
