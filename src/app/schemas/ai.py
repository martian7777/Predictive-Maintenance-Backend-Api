"""AI explanation Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnomalyStat(BaseModel):
    metric: str
    mean: float | None
    min: float | None
    max: float | None
    anomaly_mean: float | None


class AIExplanationResponse(BaseModel):
    machine_id: uuid.UUID
    machine_name: str
    machine_status: str
    model_used: str
    generated_at: datetime
    window_analyzed: int
    anomalies_found: int
    summary: str
    explanation: str
    recommendations: list[str]
    is_mock: bool
