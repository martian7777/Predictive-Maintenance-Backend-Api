"""Machine repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.machine import Machine
from app.repositories.base import BaseRepository


class MachineRepository(BaseRepository[Machine]):
    model = Machine

    async def list_for_owner(
        self, owner_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Machine]:
        stmt = (
            select(Machine)
            .where(Machine.owner_id == owner_id)
            .order_by(Machine.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_owner(self, machine_id: uuid.UUID, owner_id: uuid.UUID) -> Machine | None:
        stmt = select(Machine).where(Machine.id == machine_id, Machine.owner_id == owner_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()
