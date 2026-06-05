"""Task repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def list_for_machine(
        self, machine_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.machine_id == machine_id)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
