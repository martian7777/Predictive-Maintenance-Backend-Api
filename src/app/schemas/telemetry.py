"""Telemetry and task Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TaskStatus


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    timestamp: datetime
    temperature: float | None
    vibration: float | None
    pressure: float | None
    rotational_speed: float | None
    anomaly_score: float | None
    is_anomaly: bool


class TelemetrySeries(BaseModel):
    """Column-oriented payload optimised for plotting in the frontend."""

    machine_id: uuid.UUID
    timestamps: list[datetime]
    temperature: list[float | None]
    vibration: list[float | None]
    pressure: list[float | None]
    rotational_speed: list[float | None]
    anomaly_score: list[float | None]
    is_anomaly: list[bool]
    count: int


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    status: TaskStatus
    file_name: str
    rows_processed: int
    anomalies_detected: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    task_id: uuid.UUID
    machine_id: uuid.UUID
    status: TaskStatus
    message: str
