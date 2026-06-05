"""Direct repository-layer tests against the in-memory engine."""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest

from app.models.enums import MachineStatus, TaskStatus
from app.repositories.machine_repo import MachineRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.telemetry_repo import TelemetryRepository
from app.repositories.user_repo import UserRepository

pytestmark = pytest.mark.asyncio


async def _make_user(session):
    return await UserRepository(session).create(
        email=f"{uuid.uuid4().hex}@x.io", hashed_password="x"
    )


async def test_base_crud_roundtrip(session_factory):
    async with session_factory() as session:
        repo = UserRepository(session)
        user = await repo.create(email="crud@x.io", hashed_password="h")
        await session.commit()

        assert await repo.get(user.id) is not None
        assert await repo.get_by_email("crud@x.io") is not None
        assert await repo.count() == 1

        await repo.update(user, full_name="Renamed")
        await session.commit()
        assert (await repo.get(user.id)).full_name == "Renamed"

        listed = await repo.list(limit=10)
        assert len(listed) == 1

        await repo.delete(user)
        await session.commit()
        assert await repo.get(user.id) is None


async def test_machine_owner_scoping(session_factory):
    async with session_factory() as session:
        u1 = await _make_user(session)
        u2 = await _make_user(session)
        repo = MachineRepository(session)
        m = await repo.create(name="A", type="pump", owner_id=u1.id)
        await session.commit()

        assert await repo.get_for_owner(m.id, u1.id) is not None
        assert await repo.get_for_owner(m.id, u2.id) is None
        assert len(await repo.list_for_owner(u1.id)) == 1
        assert len(await repo.list_for_owner(u2.id)) == 0


async def test_telemetry_bulk_insert_and_stats(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        machine = await MachineRepository(session).create(
            name="M", type="motor", owner_id=user.id, status=MachineStatus.OK
        )
        await session.commit()

        repo = TelemetryRepository(session)
        from datetime import datetime

        rows = [
            {
                "id": uuid.uuid4(),
                "machine_id": machine.id,
                "timestamp": datetime(2026, 1, 1, 0, i, tzinfo=UTC),
                "temperature": 70.0 + i,
                "vibration": 0.5,
                "pressure": 30.0,
                "rotational_speed": 1500.0,
                "anomaly_score": 0.9 if i % 5 == 0 else 0.1,
                "is_anomaly": i % 5 == 0,
            }
            for i in range(20)
        ]
        inserted = await repo.bulk_insert(rows)
        await session.commit()
        assert inserted == 20

        assert await repo.count_for_machine(machine.id) == 20
        assert await repo.count_for_machine(machine.id, anomalies_only=True) == 4

        stats = await repo.stats_for_machine(machine.id)
        assert stats["telemetry_count"] == 20
        assert stats["anomaly_count"] == 4
        assert stats["last_reading_at"] is not None

        latest = await repo.latest_for_machine(machine.id, limit=5)
        assert len(latest) == 5
        # latest_for_machine returns ascending order for plotting
        assert latest[0].timestamp <= latest[-1].timestamp

        only_anom = await repo.list_for_machine(machine.id, anomalies_only=True)
        assert all(r.is_anomaly for r in only_anom)


async def test_bulk_insert_empty_returns_zero(session_factory):
    async with session_factory() as session:
        assert await TelemetryRepository(session).bulk_insert([]) == 0


async def test_task_repo_listing(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        machine = await MachineRepository(session).create(name="M", type="motor", owner_id=user.id)
        repo = TaskRepository(session)
        for _ in range(3):
            await repo.create(machine_id=machine.id, status=TaskStatus.COMPLETED, file_name="f.csv")
        await session.commit()
        assert len(await repo.list_for_machine(machine.id)) == 3
