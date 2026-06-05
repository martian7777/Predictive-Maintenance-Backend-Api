"""Telemetry repository with bulk-insert and aggregation helpers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select

from app.models.telemetry import SensorTelemetry
from app.repositories.base import BaseRepository


class TelemetryRepository(BaseRepository[SensorTelemetry]):
    model = SensorTelemetry

    async def bulk_insert(self, rows: list[dict[str, Any]]) -> int:
        """Efficiently insert many telemetry rows in one statement.

        Returns the number of rows inserted. Caller controls the transaction.
        """
        if not rows:
            return 0
        await self.session.execute(SensorTelemetry.__table__.insert(), rows)
        return len(rows)

    async def list_for_machine(
        self,
        machine_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 1000,
        anomalies_only: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[SensorTelemetry]:
        stmt = select(SensorTelemetry).where(SensorTelemetry.machine_id == machine_id)
        if anomalies_only:
            stmt = stmt.where(SensorTelemetry.is_anomaly.is_(True))
        if start is not None:
            stmt = stmt.where(SensorTelemetry.timestamp >= start)
        if end is not None:
            stmt = stmt.where(SensorTelemetry.timestamp <= end)
        stmt = stmt.order_by(SensorTelemetry.timestamp.asc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def latest_for_machine(
        self, machine_id: uuid.UUID, limit: int = 500
    ) -> list[SensorTelemetry]:
        stmt = (
            select(SensorTelemetry)
            .where(SensorTelemetry.machine_id == machine_id)
            .order_by(SensorTelemetry.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()  # return ascending for plotting
        return rows

    async def count_for_machine(self, machine_id: uuid.UUID, anomalies_only: bool = False) -> int:
        stmt = (
            select(func.count())
            .select_from(SensorTelemetry)
            .where(SensorTelemetry.machine_id == machine_id)
        )
        if anomalies_only:
            stmt = stmt.where(SensorTelemetry.is_anomaly.is_(True))
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def stats_for_machine(self, machine_id: uuid.UUID) -> dict[str, Any]:
        """Return aggregate counts + last reading timestamp for a machine."""
        anomaly_sum = func.sum(case((SensorTelemetry.is_anomaly.is_(True), 1), else_=0))
        stmt = select(
            func.count(SensorTelemetry.id),
            anomaly_sum,
            func.max(SensorTelemetry.timestamp),
        ).where(SensorTelemetry.machine_id == machine_id)
        result = await self.session.execute(stmt)
        total, anomalies, last = result.one()
        return {
            "telemetry_count": int(total or 0),
            "anomaly_count": int(anomalies or 0),
            "last_reading_at": last,
        }
