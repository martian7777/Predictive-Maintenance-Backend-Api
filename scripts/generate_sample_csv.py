#!/usr/bin/env python
"""Generate a synthetic sensor CSV for manual testing / demos.

Usage:
    python scripts/generate_sample_csv.py --rows 100000 --out sample_sensors.csv
    python scripts/generate_sample_csv.py --rows 5000000 --out big.csv   # stress test

Produces realistic temperature/vibration/pressure/rotational_speed readings with
a configurable fraction of injected anomalies (spikes / level shifts).
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd


def generate(rows: int, anomaly_frac: float, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    temperature = rng.normal(70, 1.5, rows)
    vibration = rng.normal(0.5, 0.05, rows)
    pressure = rng.normal(30, 0.8, rows)
    rotational_speed = rng.normal(1500, 20, rows)

    n_anom = int(rows * anomaly_frac)
    idx = rng.choice(rows, size=n_anom, replace=False)
    temperature[idx] += rng.normal(20, 5, n_anom)
    vibration[idx] += rng.normal(1.0, 0.3, n_anom)
    pressure[idx] -= rng.normal(8, 2, n_anom)

    timestamps = pd.date_range("2026-01-01", periods=rows, freq="s")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "temperature": temperature.round(3),
            "vibration": vibration.round(4),
            "pressure": pressure.round(3),
            "rotational_speed": rotational_speed.round(1),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a sample sensor CSV.")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--anomaly-frac", type=float, default=0.02)
    parser.add_argument("--out", type=str, default="sample_sensors.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = generate(args.rows, args.anomaly_frac, args.seed)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} rows ({args.anomaly_frac:.1%} anomalies) -> {args.out}")


if __name__ == "__main__":
    main()
