"""Telemetry pipeline tests: CSV upload, background processing, retrieval.

The background CSV task creates its own sessions via ``AsyncSessionLocal``.
We monkeypatch that module global onto the in-memory test engine so the task
and the API read/write the same database.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient

from app.services import telemetry_service
from app.services.anomaly_service import (
    FEATURE_COLUMNS,
    IsolationForestDetector,
    ZScoreDetector,
)
from app.services.telemetry_service import (
    CSVValidationError,
    TelemetryProcessor,
    _prepare_chunk,
    _validate_header,
)


def _make_csv(rows: int = 200, with_outliers: bool = True) -> bytes:
    rng = np.random.default_rng(7)
    temp = rng.normal(70, 1.5, rows)
    vib = rng.normal(0.5, 0.05, rows)
    press = rng.normal(30, 0.8, rows)
    rpm = rng.normal(1500, 20, rows)
    if with_outliers:
        for i in (20, 60, 120):
            if i < rows:
                temp[i] += 25
                vib[i] += 1.0
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="min"),
            "temperature": temp,
            "vibration": vib,
            "pressure": press,
            "rotational_speed": rpm,
        }
    )
    return df.to_csv(index=False).encode()


# ---------------------------------------------------------------- unit: detectors
def test_isolation_forest_flags_outliers():
    rng = np.random.default_rng(1)
    data = rng.normal(0, 1, (300, 4))
    data[5] = [12, 12, 12, 12]
    detector = IsolationForestDetector(contamination=0.02)
    result = detector.predict(data)
    assert result.flags.shape == (300,)
    assert result.flags[5]  # the planted outlier is detected
    assert result.scores.min() >= 0.0 and result.scores.max() <= 1.0


def test_isolation_forest_handles_nan():
    data = np.array([[1.0, np.nan, 3.0, 4.0], [2.0, 2.0, np.nan, 4.0]] * 50)
    detector = IsolationForestDetector()
    result = detector.predict(data)
    assert len(result.flags) == 100


def test_zscore_detector_baseline():
    data = np.array([[0.0]] * 100 + [[10.0]])
    detector = ZScoreDetector(threshold=3.0)
    result = detector.predict(data)
    assert result.flags[-1]


def test_detector_persistence(tmp_path):
    data = np.random.default_rng(0).normal(0, 1, (100, 4))
    detector = IsolationForestDetector()
    detector.fit(data)
    path = tmp_path / "model.joblib"
    detector.save(path)
    loaded = IsolationForestDetector.load(path)
    assert loaded.is_fitted
    np.testing.assert_array_equal(loaded.predict(data).flags, detector.predict(data).flags)


# --------------------------------------------------------------- unit: csv parsing
def test_validate_header_rejects_garbage():
    with pytest.raises(CSVValidationError):
        _validate_header(["foo", "bar"])


def test_validate_header_accepts_aliases():
    _validate_header(["time", "temp", "vib"])  # should not raise


def test_prepare_chunk_normalises_aliases():
    df = pd.read_csv(io.BytesIO(_make_csv(10)))
    df = df.rename(columns={"temperature": "temp", "rotational_speed": "rpm"})
    prepared = _prepare_chunk(df)
    for col in FEATURE_COLUMNS:
        assert col in prepared.columns
    assert prepared["timestamp"].notna().all()


def test_processor_scores_chunk():
    import uuid

    df = _prepare_chunk(pd.read_csv(io.BytesIO(_make_csv(150))))
    processor = TelemetryProcessor()
    rows, anomalies = processor.score_chunk(df, uuid.uuid4())
    assert len(rows) == 150
    assert anomalies >= 1
    assert all("anomaly_score" in r for r in rows)


# ------------------------------------------------------------- integration: upload
@pytest.fixture
def _patch_session(session_factory, monkeypatch):
    """Point the background task's session factory at the test engine."""
    monkeypatch.setattr(telemetry_service, "AsyncSessionLocal", session_factory)


async def test_upload_processes_and_persists(
    auth_client: AsyncClient, machine_id: str, _patch_session
):
    files = {"file": ("sensors.csv", _make_csv(200), "text/csv")}
    resp = await auth_client.post(f"/api/v1/telemetry/upload/{machine_id}", files=files)
    assert resp.status_code == 202
    task_id = resp.json()["task_id"]

    # ASGITransport awaits background tasks, so the task is already done.
    task = await auth_client.get(f"/api/v1/telemetry/tasks/{task_id}")
    assert task.status_code == 200
    body = task.json()
    assert body["status"] == "COMPLETED"
    assert body["rows_processed"] == 200
    assert body["anomalies_detected"] >= 1

    series = await auth_client.get(f"/api/v1/telemetry/machines/{machine_id}/series")
    assert series.status_code == 200
    assert series.json()["count"] == 200

    # Machine health should have been downgraded from OK.
    summary = await auth_client.get(f"/api/v1/machines/{machine_id}/summary")
    assert summary.json()["telemetry_count"] == 200
    assert summary.json()["status"] in ("WARNING", "CRITICAL")


async def test_series_anomalies_and_tasks_endpoints(
    auth_client: AsyncClient, machine_id: str, _patch_session
):
    files = {"file": ("sensors.csv", _make_csv(180), "text/csv")}
    await auth_client.post(f"/api/v1/telemetry/upload/{machine_id}", files=files)

    # Anomalies-only listing returns a subset of readings, all flagged.
    anomalies = await auth_client.get(f"/api/v1/telemetry/machines/{machine_id}/anomalies")
    assert anomalies.status_code == 200
    body = anomalies.json()
    assert len(body) >= 1
    assert all(r["is_anomaly"] for r in body)

    # Series respects the limit parameter.
    series = await auth_client.get(f"/api/v1/telemetry/machines/{machine_id}/series?limit=50")
    assert series.status_code == 200
    assert series.json()["count"] == 50

    # Task listing for the machine shows the completed upload.
    tasks = await auth_client.get(f"/api/v1/telemetry/machines/{machine_id}/tasks")
    assert tasks.status_code == 200
    assert len(tasks.json()) == 1
    assert tasks.json()[0]["status"] == "COMPLETED"


async def test_get_unknown_task_404(auth_client: AsyncClient):
    import uuid

    resp = await auth_client.get(f"/api/v1/telemetry/tasks/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_upload_rejects_non_csv(auth_client: AsyncClient, machine_id: str):
    files = {"file": ("data.txt", b"not a csv", "text/plain")}
    resp = await auth_client.post(f"/api/v1/telemetry/upload/{machine_id}", files=files)
    assert resp.status_code == 422


async def test_upload_with_bad_columns_marks_task_failed(
    auth_client: AsyncClient, machine_id: str, _patch_session
):
    # Valid .csv extension but no recognised sensor columns -> processing fails.
    bad = b"foo,bar\n1,2\n3,4\n"
    files = {"file": ("bad.csv", bad, "text/csv")}
    resp = await auth_client.post(f"/api/v1/telemetry/upload/{machine_id}", files=files)
    assert resp.status_code == 202
    task_id = resp.json()["task_id"]

    task = await auth_client.get(f"/api/v1/telemetry/tasks/{task_id}")
    body = task.json()
    assert body["status"] == "FAILED"
    assert body["error_message"]


async def test_upload_requires_owned_machine(auth_client: AsyncClient, _patch_session):
    import uuid

    files = {"file": ("sensors.csv", _make_csv(50), "text/csv")}
    resp = await auth_client.post(f"/api/v1/telemetry/upload/{uuid.uuid4()}", files=files)
    assert resp.status_code == 404
