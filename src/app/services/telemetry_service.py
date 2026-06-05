"""Telemetry ingestion: chunked CSV parsing, anomaly scoring, bulk persistence.

Designed for very large files (millions of rows). The CSV is streamed in
chunks via ``pandas.read_csv(chunksize=...)`` so memory stays bounded, each
chunk is scored by the anomaly detector and bulk-inserted in its own
transaction, and the owning ``Task`` row tracks progress.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.enums import MachineStatus, TaskStatus
from app.repositories.machine_repo import MachineRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.telemetry_repo import TelemetryRepository
from app.services.anomaly_service import (
    FEATURE_COLUMNS,
    IsolationForestDetector,
    get_default_detector,
)

logger = get_logger(__name__)

# Accepted CSV column aliases -> canonical model field.
COLUMN_ALIASES: dict[str, str] = {
    "timestamp": "timestamp",
    "time": "timestamp",
    "datetime": "timestamp",
    "date": "timestamp",
    "temperature": "temperature",
    "temp": "temperature",
    "vibration": "vibration",
    "vib": "vibration",
    "pressure": "pressure",
    "rotational_speed": "rotational_speed",
    "rpm": "rotational_speed",
    "speed": "rotational_speed",
}

REQUIRED_ANY = ("temperature", "vibration", "pressure", "rotational_speed")


class CSVValidationError(Exception):
    """Raised when an uploaded CSV cannot be parsed into telemetry."""


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = str(col).strip().lower().replace(" ", "_")
        if key in COLUMN_ALIASES:
            rename[col] = COLUMN_ALIASES[key]
    df = df.rename(columns=rename)
    # Keep only known canonical columns.
    keep = [c for c in ("timestamp", *FEATURE_COLUMNS) if c in df.columns]
    return df[keep]


def _validate_header(columns: list[str]) -> None:
    canonical = set()
    for col in columns:
        key = str(col).strip().lower().replace(" ", "_")
        if key in COLUMN_ALIASES:
            canonical.add(COLUMN_ALIASES[key])
    if not (canonical & set(REQUIRED_ANY)):
        raise CSVValidationError(
            "CSV must contain at least one sensor column "
            f"({', '.join(REQUIRED_ANY)}). Found: {columns}"
        )


def _prepare_chunk(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalise_columns(df)

    # Timestamp: parse or synthesise a monotonic fallback index.
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    else:
        df["timestamp"] = pd.NaT
    if df["timestamp"].isna().all():
        df["timestamp"] = pd.date_range(
            end=pd.Timestamp.utcnow(), periods=len(df), freq="s"
        )
    else:
        df["timestamp"] = df["timestamp"].ffill().fillna(pd.Timestamp.now(tz="UTC"))

    # Ensure all feature columns exist and are numeric.
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


class TelemetryProcessor:
    """Stateful processor that fits a detector on the first chunk then reuses it."""

    def __init__(self, chunk_size: int | None = None) -> None:
        self.chunk_size = chunk_size or settings.csv_chunk_size
        self._detector: IsolationForestDetector | None = None

    def _ensure_detector(self, features: np.ndarray) -> IsolationForestDetector:
        if self._detector is None:
            detector = get_default_detector()
            # get_default_detector returns the protocol type; we know concrete type.
            assert isinstance(detector, IsolationForestDetector)
            detector.fit(features)
            self._detector = detector
        return self._detector

    def score_chunk(
        self, df: pd.DataFrame, machine_id: uuid.UUID
    ) -> tuple[list[dict[str, Any]], int]:
        """Return (rows-ready-for-insert, anomaly-count) for a prepared chunk."""
        features = df[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)
        detector = self._ensure_detector(features)
        result = detector.predict(features)

        # Vectorised extraction: pull each column to a Python list once rather
        # than iterating rows (orders of magnitude faster on large chunks).
        timestamps = [ts.to_pydatetime() for ts in df["timestamp"]]
        cols = {col: df[col].to_numpy(dtype=np.float64) for col in FEATURE_COLUMNS}
        scores = result.scores
        flags = result.flags

        rows: list[dict[str, Any]] = [
            {
                "id": uuid.uuid4(),
                "machine_id": machine_id,
                "timestamp": timestamps[i],
                "temperature": _nan_to_none(cols["temperature"][i]),
                "vibration": _nan_to_none(cols["vibration"][i]),
                "pressure": _nan_to_none(cols["pressure"][i]),
                "rotational_speed": _nan_to_none(cols["rotational_speed"][i]),
                "anomaly_score": float(scores[i]),
                "is_anomaly": bool(flags[i]),
            }
            for i in range(len(df))
        ]
        return rows, int(flags.sum())


def _nan_to_none(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


async def process_csv_task(
    task_id: uuid.UUID, machine_id: uuid.UUID, file_path: str
) -> None:
    """Background entry point: parse a CSV file and persist scored telemetry.

    Runs with its own DB session (the request session is already closed).
    Never raises — failures are recorded on the Task row.
    """
    processor = TelemetryProcessor()
    total_rows = 0
    total_anomalies = 0

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        task = await task_repo.get(task_id)
        if task is None:
            logger.error("task_not_found", task_id=str(task_id))
            return
        await task_repo.update(task, status=TaskStatus.PROCESSING)
        await session.commit()

    try:
        _validate_header(_read_header(file_path))

        reader = pd.read_csv(
            file_path,
            chunksize=processor.chunk_size,
            iterator=True,
        )
        for chunk in reader:
            prepared = _prepare_chunk(chunk)
            if prepared.empty:
                continue
            rows, anomalies = processor.score_chunk(prepared, machine_id)

            async with AsyncSessionLocal() as session:
                tel_repo = TelemetryRepository(session)
                inserted = await tel_repo.bulk_insert(rows)
                await session.commit()

            total_rows += inserted
            total_anomalies += anomalies

            async with AsyncSessionLocal() as session:
                task_repo = TaskRepository(session)
                task = await task_repo.get(task_id)
                if task:
                    await task_repo.update(
                        task,
                        rows_processed=total_rows,
                        anomalies_detected=total_anomalies,
                    )
                    await session.commit()

        await _finalise(task_id, machine_id, total_rows, total_anomalies)
        logger.info(
            "csv_task_completed",
            task_id=str(task_id),
            rows=total_rows,
            anomalies=total_anomalies,
        )

    except Exception as exc:  # noqa: BLE001 - background task must not crash
        logger.exception("csv_task_failed", task_id=str(task_id))
        async with AsyncSessionLocal() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get(task_id)
            if task:
                await task_repo.update(
                    task,
                    status=TaskStatus.FAILED,
                    error_message=str(exc)[:1000],
                    rows_processed=total_rows,
                    anomalies_detected=total_anomalies,
                )
                await session.commit()
    finally:
        _cleanup_file(file_path)


async def _finalise(
    task_id: uuid.UUID, machine_id: uuid.UUID, total_rows: int, total_anomalies: int
) -> None:
    """Mark the task complete and derive the machine's health status."""
    ratio = (total_anomalies / total_rows) if total_rows else 0.0
    if ratio >= 0.10:
        status = MachineStatus.CRITICAL
    elif ratio >= 0.02 or total_anomalies > 0:
        status = MachineStatus.WARNING
    else:
        status = MachineStatus.OK

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        machine_repo = MachineRepository(session)
        task = await task_repo.get(task_id)
        if task:
            await task_repo.update(
                task,
                status=TaskStatus.COMPLETED,
                rows_processed=total_rows,
                anomalies_detected=total_anomalies,
            )
        machine = await machine_repo.get(machine_id)
        if machine:
            await machine_repo.update(machine, status=status)
        await session.commit()


def _read_header(file_path: str) -> list[str]:
    head = pd.read_csv(file_path, nrows=0)
    return [str(c) for c in head.columns]


def _cleanup_file(file_path: str) -> None:
    try:
        Path(file_path).unlink(missing_ok=True)
    except OSError:  # pragma: no cover
        logger.warning("temp_file_cleanup_failed", file=file_path)
