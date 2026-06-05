"""AI explanation tests (uses the built-in mock explainer; no network)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import telemetry_service

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _patch_session(session_factory, monkeypatch):
    monkeypatch.setattr(telemetry_service, "AsyncSessionLocal", session_factory)


def _csv(rows: int = 150) -> bytes:
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(3)
    temp = rng.normal(70, 1.0, rows)
    temp[10] += 30
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="min"),
            "temperature": temp,
            "vibration": rng.normal(0.5, 0.05, rows),
            "pressure": rng.normal(30, 0.5, rows),
            "rotational_speed": rng.normal(1500, 10, rows),
        }
    )
    return df.to_csv(index=False).encode()


async def test_explain_no_data_returns_mock(auth_client: AsyncClient, machine_id: str):
    resp = await auth_client.get(f"/api/v1/ai/explain/{machine_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_mock"] is True
    assert body["model_used"] == "mock"
    assert body["anomalies_found"] == 0
    assert isinstance(body["recommendations"], list)


async def test_explain_after_upload(auth_client: AsyncClient, machine_id: str, _patch_session):
    files = {"file": ("sensors.csv", _csv(150), "text/csv")}
    await auth_client.post(f"/api/v1/telemetry/upload/{machine_id}", files=files)

    resp = await auth_client.get(f"/api/v1/ai/explain/{machine_id}?window=200")
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_analyzed"] == 150
    assert body["anomalies_found"] >= 1
    assert len(body["recommendations"]) >= 1
    assert body["machine_name"] == "Pump-1"


async def test_explain_requires_auth(client: AsyncClient):
    import uuid

    resp = await client.get(f"/api/v1/ai/explain/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_explain_uses_openrouter_when_enabled(
    auth_client: AsyncClient, machine_id: str, monkeypatch
):
    """When a key is configured, the OpenRouter path is used and parsed."""
    import json as _json
    import types

    from app.core import config as config_module
    from app.services import ai_service as ai_module

    # Pretend AI is enabled.
    monkeypatch.setattr(config_module.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_module.settings, "openrouter_api_key", "test-key")

    payload = {
        "summary": "Bearing wear detected.",
        "explanation": "Vibration trending up.",
        "recommendations": ["Inspect bearings", "Re-lubricate"],
    }

    class _FakeCompletions:
        async def create(self, **kwargs):
            msg = types.SimpleNamespace(content=_json.dumps(payload))
            choice = types.SimpleNamespace(message=msg)
            return types.SimpleNamespace(choices=[choice])

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *a, **k):
            self.chat = _FakeChat()

    import openai

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeClient)

    resp = await auth_client.get(f"/api/v1/ai/explain/{machine_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_mock"] is False
    assert body["summary"] == "Bearing wear detected."
    assert "Inspect bearings" in body["recommendations"]
