"""Machine business logic: CRUD scoped to an owner, plus rolled-up summaries."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.machine import Machine
from app.repositories.machine_repo import MachineRepository
from app.repositories.telemetry_repo import TelemetryRepository
from app.schemas.machine import MachineCreate, MachineRead, MachineSummary, MachineUpdate


class MachineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.machines = MachineRepository(session)
        self.telemetry = TelemetryRepository(session)

    async def create(self, owner_id: uuid.UUID, data: MachineCreate) -> Machine:
        return await self.machines.create(
            name=data.name,
            type=data.type,
            location=data.location,
            owner_id=owner_id,
        )

    async def get_owned(self, machine_id: uuid.UUID, owner_id: uuid.UUID) -> Machine:
        machine = await self.machines.get_for_owner(machine_id, owner_id)
        if machine is None:
            raise NotFoundError("Machine not found")
        return machine

    async def list_owned(
        self, owner_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Machine]:
        return await self.machines.list_for_owner(owner_id, skip=skip, limit=limit)

    async def update(
        self, machine_id: uuid.UUID, owner_id: uuid.UUID, data: MachineUpdate
    ) -> Machine:
        machine = await self.get_owned(machine_id, owner_id)
        changes = data.model_dump(exclude_unset=True)
        return await self.machines.update(machine, **changes)

    async def delete(self, machine_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        machine = await self.get_owned(machine_id, owner_id)
        await self.machines.delete(machine)

    async def summary(self, machine_id: uuid.UUID, owner_id: uuid.UUID) -> MachineSummary:
        machine = await self.get_owned(machine_id, owner_id)
        stats = await self.telemetry.stats_for_machine(machine_id)
        return MachineSummary(
            **MachineRead.model_validate(machine).model_dump(),
            telemetry_count=stats["telemetry_count"],
            anomaly_count=stats["anomaly_count"],
            last_reading_at=stats["last_reading_at"],
        )
