"""Sensor telemetry ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.machine import Machine


class SensorTelemetry(UUIDMixin, Base):
    __tablename__ = "sensor_telemetry"

    machine_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotational_speed: Mapped[float | None] = mapped_column(Float, nullable=True)

    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    machine: Mapped["Machine"] = relationship(back_populates="telemetry")

    __table_args__ = (
        # Most common access pattern: a machine's readings within a time window.
        Index("ix_telemetry_machine_timestamp", "machine_id", "timestamp"),
        Index("ix_telemetry_machine_anomaly", "machine_id", "is_anomaly"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Telemetry machine={self.machine_id} t={self.timestamp} anomaly={self.is_anomaly}>"
