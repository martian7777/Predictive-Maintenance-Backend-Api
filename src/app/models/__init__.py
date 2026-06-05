"""ORM models. Import all models here so Alembic autogenerate can discover them."""

from app.models.base import Base
from app.models.enums import MachineStatus, TaskStatus
from app.models.machine import Machine
from app.models.task import Task
from app.models.telemetry import SensorTelemetry
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Machine",
    "SensorTelemetry",
    "Task",
    "MachineStatus",
    "TaskStatus",
]
