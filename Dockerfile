# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Multi-stage image shared by the FastAPI backend and the Gradio frontend.
# ---------------------------------------------------------------------------

# ----- base: common runtime with dependencies -----------------------------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps required by asyncpg / scikit-learn wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

# Install the project (runtime deps only).
RUN pip install --upgrade pip && pip install .

# ----- dev/test: adds dev dependencies and test tooling --------------------
FROM base AS dev
RUN pip install ".[dev]"
COPY alembic.ini ./
COPY alembic ./alembic
CMD ["pytest", "-v"]

# ----- api: FastAPI server -------------------------------------------------
FROM base AS api
COPY alembic.ini ./
COPY alembic ./alembic
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ----- frontend: Gradio app ------------------------------------------------
FROM base AS frontend
EXPOSE 7860
CMD ["python", "-m", "frontend.app"]
