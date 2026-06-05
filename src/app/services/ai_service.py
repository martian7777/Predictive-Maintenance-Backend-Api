"""OpenRouter-backed AI explanation service with a deterministic mock fallback.

Builds a compact, structured context window from a machine's most recent
telemetry (emphasising anomalous readings) and asks an LLM to explain likely
root causes and recommend maintenance actions. When no OpenRouter API key is
configured it returns a rule-based mock so the system is fully usable offline.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from statistics import fmean
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.machine import Machine
from app.repositories.machine_repo import MachineRepository
from app.repositories.telemetry_repo import TelemetryRepository
from app.schemas.ai import AIExplanationResponse
from app.services.anomaly_service import FEATURE_COLUMNS

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert industrial reliability and predictive-maintenance engineer. "
    "You analyse multivariate sensor telemetry (temperature, vibration, pressure, "
    "rotational speed) and explain anomalies in clear, actionable terms. "
    "Respond ONLY with a JSON object matching this schema: "
    '{"summary": string, "explanation": string, "recommendations": [string, ...]}. '
    "Keep the summary to one sentence. Provide 3-6 concrete recommendations."
)


class AIService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.machines = MachineRepository(session)
        self.telemetry = TelemetryRepository(session)

    async def explain_machine(
        self, machine_id: uuid.UUID, owner_id: uuid.UUID, window: int = 500
    ) -> AIExplanationResponse:
        machine = await self.machines.get_for_owner(machine_id, owner_id)
        if machine is None:
            raise NotFoundError("Machine not found")

        readings = await self.telemetry.latest_for_machine(machine_id, limit=window)
        context = self._build_context(machine, readings)

        if settings.ai_enabled:
            try:
                content, model_used, is_mock = await self._call_openrouter(context)
            except Exception:  # noqa: BLE001 - degrade gracefully to mock
                logger.exception("openrouter_call_failed")
                content, model_used, is_mock = self._mock_explanation(context), "mock", True
        else:
            content, model_used, is_mock = self._mock_explanation(context), "mock", True

        return AIExplanationResponse(
            machine_id=machine.id,
            machine_name=machine.name,
            machine_status=machine.status.value,
            model_used=model_used,
            generated_at=datetime.now(UTC),
            window_analyzed=context["analyzed"],
            anomalies_found=context["anomaly_count"],
            summary=content["summary"],
            explanation=content["explanation"],
            recommendations=content["recommendations"],
            is_mock=is_mock,
        )

    # ------------------------------------------------------------------ context
    def _build_context(self, machine: Machine, readings: list) -> dict[str, Any]:
        anomalies = [r for r in readings if r.is_anomaly]
        metrics: dict[str, dict[str, float | None]] = {}
        for col in FEATURE_COLUMNS:
            all_vals = [getattr(r, col) for r in readings if getattr(r, col) is not None]
            anom_vals = [getattr(r, col) for r in anomalies if getattr(r, col) is not None]
            metrics[col] = {
                "mean": round(fmean(all_vals), 3) if all_vals else None,
                "min": round(min(all_vals), 3) if all_vals else None,
                "max": round(max(all_vals), 3) if all_vals else None,
                "anomaly_mean": round(fmean(anom_vals), 3) if anom_vals else None,
            }

        sample_anomalies = [
            {
                "timestamp": r.timestamp.isoformat(),
                "temperature": r.temperature,
                "vibration": r.vibration,
                "pressure": r.pressure,
                "rotational_speed": r.rotational_speed,
                "anomaly_score": round(r.anomaly_score, 3) if r.anomaly_score else None,
            }
            for r in anomalies[:15]
        ]

        return {
            "machine": {
                "name": machine.name,
                "type": machine.type,
                "location": machine.location,
                "status": machine.status.value,
            },
            "analyzed": len(readings),
            "anomaly_count": len(anomalies),
            "metrics": metrics,
            "sample_anomalies": sample_anomalies,
        }

    # ------------------------------------------------------------------ openrouter
    async def _call_openrouter(
        self, context: dict[str, Any]
    ) -> tuple[dict[str, Any], str, bool]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=settings.openrouter_timeout_seconds,
            default_headers={
                "HTTP-Referer": settings.api_base_url,
                "X-Title": settings.app_name,
            },
        )

        user_prompt = (
            "Analyse the following predictive-maintenance telemetry context and "
            "return the JSON object as instructed.\n\n"
            f"{json.dumps(context, default=str)}"
        )

        models = [settings.openrouter_model, settings.openrouter_fallback_model]
        last_error: Exception | None = None
        for model in models:
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content or "{}"
                return self._parse_ai_json(raw), model, False
            except Exception as exc:  # noqa: BLE001 - try fallback model next
                last_error = exc
                logger.warning("openrouter_model_failed", model=model, error=str(exc))
        raise last_error or RuntimeError("OpenRouter call failed")

    @staticmethod
    def _parse_ai_json(raw: str) -> dict[str, Any]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Best-effort: wrap unstructured text.
            return {
                "summary": "AI returned unstructured output.",
                "explanation": raw[:2000],
                "recommendations": [],
            }
        return {
            "summary": str(data.get("summary", "")),
            "explanation": str(data.get("explanation", "")),
            "recommendations": [str(r) for r in data.get("recommendations", [])],
        }

    # ------------------------------------------------------------------ mock
    @staticmethod
    def _mock_explanation(context: dict[str, Any]) -> dict[str, Any]:
        anomaly_count = context["anomaly_count"]
        analyzed = context["analyzed"]
        metrics = context["metrics"]
        machine = context["machine"]

        drivers: list[str] = []
        for col, stat in metrics.items():
            if stat["anomaly_mean"] is not None and stat["mean"] is not None:
                delta = stat["anomaly_mean"] - stat["mean"]
                if abs(delta) > 1e-6 and stat["mean"] != 0:
                    pct = (delta / abs(stat["mean"])) * 100
                    if abs(pct) >= 5:
                        direction = "elevated" if delta > 0 else "depressed"
                        drivers.append(f"{col} is {direction} by {abs(pct):.0f}% during anomalies")

        if anomaly_count == 0:
            summary = f"{machine['name']} is operating within normal parameters."
            explanation = (
                f"Across the last {analyzed} readings no anomalies were detected. "
                "Sensor values remained within the learned baseline distribution."
            )
            recommendations = [
                "Continue routine monitoring at the current cadence.",
                "Re-train the baseline model periodically as operating conditions evolve.",
            ]
        else:
            ratio = anomaly_count / analyzed if analyzed else 0
            driver_text = "; ".join(drivers) if drivers else "multiple correlated sensor deviations"
            summary = (
                f"{anomaly_count} anomalies in the last {analyzed} readings "
                f"({ratio:.1%}) on {machine['name']}."
            )
            explanation = (
                f"The Isolation Forest detector flagged {anomaly_count} readings as "
                f"out-of-distribution. Primary drivers: {driver_text}. This pattern is "
                "consistent with developing mechanical wear, lubrication degradation, or "
                "load imbalance and warrants inspection before failure escalates."
            )
            recommendations = [
                "Schedule a physical inspection of bearings and mounts for vibration sources.",
                "Verify cooling/lubrication systems given temperature deviations.",
                "Check load balancing and operating setpoints against rated limits.",
                "Increase sampling frequency on this asset until readings stabilise.",
            ]
            if ratio >= 0.10:
                recommendations.insert(
                    0, "URGENT: anomaly rate exceeds 10% — consider taking the asset offline."
                )

        return {
            "summary": summary,
            "explanation": explanation,
            "recommendations": recommendations,
        }
