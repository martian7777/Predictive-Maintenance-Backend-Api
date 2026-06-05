"""Pluggable anomaly detection.

The `AnomalyDetector` protocol defines a stable interface so detection backends
can be swapped (statistical Z-score baseline, Isolation Forest, a deep model)
without touching the telemetry pipeline. `IsolationForestDetector` is the
default, production-grade implementation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Feature order is fixed and shared between training and inference.
FEATURE_COLUMNS: tuple[str, ...] = (
    "temperature",
    "vibration",
    "pressure",
    "rotational_speed",
)


class DetectionResult:
    """Container for per-row scores and boolean anomaly flags."""

    __slots__ = ("scores", "flags")

    def __init__(self, scores: np.ndarray, flags: np.ndarray) -> None:
        self.scores = scores
        self.flags = flags


@runtime_checkable
class AnomalyDetector(Protocol):
    """Interface every detection backend must satisfy."""

    def fit(self, features: np.ndarray) -> None: ...

    def predict(self, features: np.ndarray) -> DetectionResult: ...

    @property
    def is_fitted(self) -> bool: ...


class ZScoreDetector:
    """Simple statistical baseline: flag rows whose worst feature |z| > threshold.

    Useful as a dependency-light fallback and for unit tests.
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self.threshold = threshold
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None

    @property
    def is_fitted(self) -> bool:
        return self._mean is not None

    def fit(self, features: np.ndarray) -> None:
        self._mean = features.mean(axis=0)
        self._std = features.std(axis=0) + 1e-9

    def predict(self, features: np.ndarray) -> DetectionResult:
        if not self.is_fitted:
            self.fit(features)
        assert self._mean is not None and self._std is not None
        z = np.abs((features - self._mean) / self._std)
        worst = z.max(axis=1)
        flags = worst > self.threshold
        # Higher score => more anomalous, normalised loosely to [0, 1].
        scores = np.clip(worst / (self.threshold * 2), 0.0, 1.0)
        return DetectionResult(scores=scores, flags=flags)


class IsolationForestDetector:
    """Isolation Forest detector with feature scaling and persistence.

    The model is fit on the data it scores (unsupervised), which suits batch
    telemetry uploads where a per-machine baseline is established from the file
    itself. Trained models are persisted per machine so they can be reused.
    """

    def __init__(
        self,
        contamination: float | None = None,
        n_estimators: int | None = None,
        random_state: int = 42,
    ) -> None:
        self.contamination = (
            contamination
            if contamination is not None
            else settings.isolation_forest_contamination
        )
        self.n_estimators = (
            n_estimators
            if n_estimators is not None
            else settings.isolation_forest_n_estimators
        )
        self.random_state = random_state
        self._scaler = StandardScaler()
        self._model: IsolationForest | None = None

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    def fit(self, features: np.ndarray) -> None:
        features = self._clean(features)
        scaled = self._scaler.fit_transform(features)
        self._model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(scaled)
        logger.info(
            "isolation_forest_fit",
            rows=int(features.shape[0]),
            contamination=self.contamination,
            n_estimators=self.n_estimators,
        )

    def predict(self, features: np.ndarray) -> DetectionResult:
        features = self._clean(features)
        if not self.is_fitted:
            self.fit(features)
        assert self._model is not None
        scaled = self._scaler.transform(features)
        # decision_function: higher = more normal. Flip + normalise so higher = anomalous.
        raw = self._model.decision_function(scaled)
        preds = self._model.predict(scaled)  # -1 anomaly, 1 normal
        scores = self._normalise_scores(raw)
        flags = preds == -1
        return DetectionResult(scores=scores, flags=flags)

    @staticmethod
    def _clean(features: np.ndarray) -> np.ndarray:
        """Replace NaN/inf with column means so the model stays numerically stable."""
        features = np.asarray(features, dtype=np.float64)
        if features.ndim == 1:
            features = features.reshape(-1, 1)
        col_means = np.nanmean(
            np.where(np.isfinite(features), features, np.nan), axis=0
        )
        col_means = np.where(np.isfinite(col_means), col_means, 0.0)
        idx = ~np.isfinite(features)
        features[idx] = np.take(col_means, np.where(idx)[1])
        return features

    @staticmethod
    def _normalise_scores(raw: np.ndarray) -> np.ndarray:
        """Map decision-function output to a [0, 1] anomaly score (1 = most anomalous)."""
        inverted = -raw
        lo, hi = inverted.min(), inverted.max()
        if hi - lo < 1e-12:
            return np.full_like(inverted, 0.5)
        return (inverted - lo) / (hi - lo)

    # --- persistence ---
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self._model, "scaler": self._scaler, "contamination": self.contamination},
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> IsolationForestDetector:
        data = joblib.load(path)
        detector = cls(contamination=data.get("contamination"))
        detector._model = data["model"]
        detector._scaler = data["scaler"]
        return detector


def get_default_detector() -> AnomalyDetector:
    """Factory for the configured default detector backend."""
    return IsolationForestDetector()
