"""Machine Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MachineStatus


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=128)
    location: str | None = Field(default=None, max_length=255)


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, min_length=1, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    status: MachineStatus | None = None


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    location: str | None
    status: MachineStatus
    owner_id: uuid.UUID
    created_at: datetime


class MachineSummary(MachineRead):
    """Machine plus rolled-up telemetry/anomaly statistics."""

    telemetry_count: int = 0
    anomaly_count: int = 0
    last_reading_at: datetime | None = None
