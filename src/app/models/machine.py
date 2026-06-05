"""Machine ORM model."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TimestampMixin, UUIDMixin
from app.models.enums import MachineStatus

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.telemetry import SensorTelemetry
    from app.models.user import User


class Machine(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "machines"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MachineStatus] = mapped_column(
        SAEnum(MachineStatus, name="machine_status"),
        default=MachineStatus.OK,
        nullable=False,
        index=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner: Mapped[User] = relationship(back_populates="machines")
    telemetry: Mapped[list[SensorTelemetry]] = relationship(
        back_populates="machine",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="machine",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Machine {self.name} ({self.status})>"
