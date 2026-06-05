# 🛠️ Predictive Maintenance Platform

A production-grade predictive maintenance system: a **FastAPI** backend with
**Isolation Forest** anomaly detection, chunked ingestion of multi-million-row
sensor CSVs, **OpenRouter (Gemini)** AI maintenance reports, and a multi-tab
**Gradio** web frontend.

![status](https://img.shields.io/badge/build-CI-green) ![python](https://img.shields.io/badge/python-3.11+-blue)

---

## Features

- **JWT auth** (OAuth2 password flow) with per-user machine isolation.
- **Machine registry** with health status (`OK` / `WARNING` / `CRITICAL`).
- **Large-scale CSV ingestion** — streamed in chunks (`pandas` `chunksize`),
  scored, and bulk-inserted in transactional batches so RAM stays bounded.
- **Isolation Forest anomaly detection** behind a pluggable `AnomalyDetector`
  interface (Z-score baseline also included; swap backends without touching the
  pipeline).
- **Background processing** with a `Task` row tracking `PENDING → PROCESSING →
  COMPLETED / FAILED` plus row and anomaly counts.
- **AI explanations** via OpenRouter (`google/gemini-2.5-pro`, with a
  `gemini-2.5-flash` fallback). Falls back to a deterministic rule-based
  explainer when no API key is set — fully usable offline.
- **Interactive Gradio UI** — register machines, upload CSVs with live progress,
  Plotly time-series charts with anomalies highlighted, and on-demand AI reports.
- **Async SQLAlchemy 2.0 + Alembic** migrations against PostgreSQL.
- **Tested** with an in-memory SQLite suite (no Postgres/network needed) and CI.

---

## Quick start (Docker)

```bash
cp .env.example .env          # then edit secrets / OpenRouter key
docker-compose up --build
```

- API + docs: <http://localhost:8000/docs>
- Gradio UI:  <http://localhost:7860>

The `api` container runs `alembic upgrade head` automatically on start.

## Quick start (local)

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

# Start Postgres (e.g. via docker) then:
python run.py migrate          # apply migrations
python run.py                  # starts API (8000) + Gradio (7860)
```

## Running tests

```bash
pytest                         # in-memory SQLite, no external services
pytest --cov=app --cov-report=term-missing
```

---

## End-to-end user journey

1. **Register / log in** on the *Dashboard & Auth* tab.
2. **Create a machine** (name, type, location).
3. **Upload a sensor CSV** on the *Telemetry Upload* tab and watch the task progress.
4. **Visualise** temperature/vibration with anomalies highlighted on *Analytics*.
5. **Generate an AI maintenance report** on the *AI Assistant* tab.

### Expected CSV format

| timestamp | temperature | vibration | pressure | rotational_speed |
|-----------|-------------|-----------|----------|------------------|
| 2026-01-01T00:00:00 | 70.2 | 0.51 | 30.1 | 1500 |

Column aliases are accepted (`temp`, `vib`, `rpm`, `time`, …) and at least one
sensor column is required. Missing values are imputed; missing timestamps are
synthesised as a monotonic series.

---

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — layered design, data flow, decisions.
- **[WIKI.md](WIKI.md)** — full setup, DB schema, API reference, operations, deployment.

## Project layout

```
src/app          FastAPI backend (api / core / models / schemas / repositories / services)
src/frontend     Gradio UI + API client
src/tests        Pytest suite
alembic          Async migrations
```

## License

MIT
