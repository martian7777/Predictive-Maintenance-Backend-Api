"""Shared / generic Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Message(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str
    ai_enabled: bool


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)
