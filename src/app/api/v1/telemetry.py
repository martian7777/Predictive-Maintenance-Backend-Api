"""Telemetry endpoints: CSV upload, task polling, time-series retrieval."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status

from app.api.dependencies import CurrentUser, DbSession
from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import TaskStatus
from app.repositories.task_repo import TaskRepository
from app.repositories.telemetry_repo import TelemetryRepository
from app.schemas.telemetry import (
    TaskRead,
    TelemetryRead,
    TelemetrySeries,
    UploadResponse,
)
from app.services.machine_service import MachineService
from app.services.telemetry_service import process_csv_task

router = APIRouter()

UPLOAD_DIR = Path(tempfile.gettempdir()) / "pm_uploads"


@router.post(
    "/upload/{machine_id}",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_telemetry(
    machine_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    # Authorise: the machine must belong to the caller.
    await MachineService(session).get_owned(machine_id, current_user.id)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise ValidationError("Only .csv files are accepted")

    # Stream the upload to a temp file so multi-GB CSVs never sit in RAM.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4()}_{Path(file.filename).name}"
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    await file.close()

    task = await TaskRepository(session).create(
        machine_id=machine_id,
        status=TaskStatus.PENDING,
        file_name=file.filename,
    )
    # Commit now so the task row is visible before the background job starts.
    await session.commit()

    background_tasks.add_task(process_csv_task, task.id, machine_id, str(dest))

    return UploadResponse(
        task_id=task.id,
        machine_id=machine_id,
        status=TaskStatus.PENDING,
        message="Upload accepted. Processing started in the background.",
    )


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> TaskRead:
    task = await TaskRepository(session).get(task_id)
    if task is None:
        raise NotFoundError("Task not found")
    # Ensure the task's machine belongs to the caller.
    await MachineService(session).get_owned(task.machine_id, current_user.id)
    return TaskRead.model_validate(task)


@router.get("/machines/{machine_id}/tasks", response_model=list[TaskRead])
async def list_machine_tasks(
    machine_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[TaskRead]:
    await MachineService(session).get_owned(machine_id, current_user.id)
    tasks = await TaskRepository(session).list_for_machine(machine_id)
    return [TaskRead.model_validate(t) for t in tasks]


@router.get("/machines/{machine_id}/series", response_model=TelemetrySeries)
async def get_telemetry_series(
    machine_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: int = Query(1000, ge=1, le=20000),
) -> TelemetrySeries:
    """Return the most recent readings as parallel arrays for charting."""
    await MachineService(session).get_owned(machine_id, current_user.id)
    rows = await TelemetryRepository(session).latest_for_machine(machine_id, limit=limit)
    return TelemetrySeries(
        machine_id=machine_id,
        timestamps=[r.timestamp for r in rows],
        temperature=[r.temperature for r in rows],
        vibration=[r.vibration for r in rows],
        pressure=[r.pressure for r in rows],
        rotational_speed=[r.rotational_speed for r in rows],
        anomaly_score=[r.anomaly_score for r in rows],
        is_anomaly=[r.is_anomaly for r in rows],
        count=len(rows),
    )


@router.get("/machines/{machine_id}/anomalies", response_model=list[TelemetryRead])
async def list_anomalies(
    machine_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: int = Query(200, ge=1, le=5000),
) -> list[TelemetryRead]:
    await MachineService(session).get_owned(machine_id, current_user.id)
    rows = await TelemetryRepository(session).list_for_machine(
        machine_id, anomalies_only=True, limit=limit
    )
    return [TelemetryRead.model_validate(r) for r in rows]
