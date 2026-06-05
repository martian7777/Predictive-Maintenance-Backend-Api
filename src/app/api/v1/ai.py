"""AI explanation endpoints (OpenRouter / Gemini with mock fallback)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.ai import AIExplanationResponse
from app.services.ai_service import AIService

router = APIRouter()


@router.get("/explain/{machine_id}", response_model=AIExplanationResponse)
async def explain_machine(
    machine_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    window: int = Query(500, ge=10, le=5000, description="Number of recent readings to analyse"),
) -> AIExplanationResponse:
    return await AIService(session).explain_machine(
        machine_id, current_user.id, window=window
    )
