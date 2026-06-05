#!/usr/bin/env python
"""Convenience orchestrator to start the API and the Gradio frontend together.

Usage:
    python run.py                # start both API + frontend
    python run.py api            # start only the FastAPI backend
    python run.py frontend       # start only the Gradio frontend
    python run.py migrate        # run alembic migrations to head

This script assumes PostgreSQL is already reachable (e.g. via `docker-compose up db`).
For a fully containerised stack use `docker-compose up` instead.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ENV = {**os.environ, "PYTHONPATH": str(SRC)}


def _spawn(args: list[str], name: str) -> subprocess.Popen:
    print(f"[run] starting {name}: {' '.join(args)}")
    return subprocess.Popen(args, env=ENV, cwd=ROOT)


def run_migrate() -> int:
    return subprocess.call(["alembic", "upgrade", "head"], env=ENV, cwd=ROOT)


def run_api() -> subprocess.Popen:
    host = os.getenv("API_HOST", "0.0.0.0")
    port = os.getenv("API_PORT", "8000")
    return _spawn(
        ["uvicorn", "app.main:app", "--host", host, "--port", port, "--reload"],
        "api",
    )


def run_frontend() -> subprocess.Popen:
    return _spawn([sys.executable, "-m", "frontend.app"], "frontend")


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target == "migrate":
        return run_migrate()

    procs: list[subprocess.Popen] = []
    try:
        if target in ("all", "api"):
            procs.append(run_api())
        if target == "all":
            time.sleep(2)  # give the API a moment to bind before the UI connects
        if target in ("all", "frontend"):
            procs.append(run_frontend())

        if not procs:
            print(f"[run] unknown target '{target}'. Use api|frontend|migrate|all.")
            return 1

        # Wait until any child exits, then tear the rest down.
        while True:
            for p in procs:
                if p.poll() is not None:
                    raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[run] shutting down...")
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
