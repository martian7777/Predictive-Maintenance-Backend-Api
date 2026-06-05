"""Machine CRUD endpoints (scoped to the authenticated owner)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.machine import (
    MachineCreate,
    MachineRead,
    MachineSummary,
    MachineUpdate,
)
from app.services.machine_service import MachineService

router = APIRouter()


@router.post("", response_model=MachineRead, status_code=status.HTTP_201_CREATED)
async def create_machine(
    data: MachineCreate, current_user: CurrentUser, session: DbSession
) -> MachineRead:
    machine = await MachineService(session).create(current_user.id, data)
    return MachineRead.model_validate(machine)


@router.get("", response_model=list[MachineRead])
async def list_machines(
    current_user: CurrentUser,
    session: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[MachineRead]:
    machines = await MachineService(session).list_owned(current_user.id, skip=skip, limit=limit)
    return [MachineRead.model_validate(m) for m in machines]


@router.get("/{machine_id}", response_model=MachineRead)
async def get_machine(
    machine_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> MachineRead:
    machine = await MachineService(session).get_owned(machine_id, current_user.id)
    return MachineRead.model_validate(machine)


@router.get("/{machine_id}/summary", response_model=MachineSummary)
async def get_machine_summary(
    machine_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> MachineSummary:
    return await MachineService(session).summary(machine_id, current_user.id)


@router.patch("/{machine_id}", response_model=MachineRead)
async def update_machine(
    machine_id: uuid.UUID,
    data: MachineUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> MachineRead:
    machine = await MachineService(session).update(machine_id, current_user.id, data)
    return MachineRead.model_validate(machine)


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine(
    machine_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    await MachineService(session).delete(machine_id, current_user.id)
