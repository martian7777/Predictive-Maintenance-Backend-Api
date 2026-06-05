"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import ai, auth, machines, telemetry

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(machines.router, prefix="/machines", tags=["machines"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
