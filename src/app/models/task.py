"""Background processing task ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TimestampMixin, UUIDMixin
from app.models.enums import TaskStatus

if TYPE_CHECKING:
    from app.models.machine import Machine


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    machine_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anomalies_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    machine: Mapped[Machine] = relationship(back_populates="tasks")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task {self.id} {self.status} rows={self.rows_processed}>"
