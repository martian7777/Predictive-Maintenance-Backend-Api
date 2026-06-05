# 🛠️ Predictive Maintenance Platform

A production-grade, end-to-end predictive maintenance system featuring a high-performance **FastAPI** backend, unsupervised **Isolation Forest** anomaly detection, streamlined chunked ingestion of multi-million-row sensor data, **OpenRouter (Gemini)** powered AI maintenance reports, and an interactive **Gradio** web dashboard.

---

<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://gradio.app"><img src="https://img.shields.io/badge/Gradio-FF9D00?style=for-the-badge&logo=gradio&logoColor=white" alt="Gradio UI" /></a>
  <a href="https://scikit-learn.org"><img src="https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="scikit-learn" /></a>
  <a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <br/>
  <a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" /></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-ruff-black?style=for-the-badge&logo=python&logoColor=white" alt="Ruff" /></a>
  <a href="https://pytest.org"><img src="https://img.shields.io/badge/tests-pytest-green?style=for-the-badge&logo=pytest&logoColor=white" alt="Pytest" /></a>
</p>

---

## 🗺️ System Topology & Data Flow

```mermaid
graph TD
    %% Custom Styles %%
    classDef client fill:#334155,stroke:#94a3b8,stroke-width:2px,color:#f8fafc;
    classDef frontend fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#f8fafc;
    classDef backend fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef db fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef external fill:#1e293b,stroke:#a855f7,stroke-width:2px,color:#f8fafc;

    User([User Browser]) :::client
    Gradio[Gradio Web UI<br/>(Port 7860)] :::frontend
    FastAPI[FastAPI Backend API<br/>(Port 8000)] :::backend
    Postgres[(PostgreSQL DB<br/>Sensor & Machine Registry)] :::db
    OpenRouter[OpenRouter Gemini API<br/>(AI Explanations)] :::external
    LocalModel[Local Isolation Forest<br/>(Scikit-Learn ML Model)] :::backend

    User -->|HTTPS| Gradio
    Gradio -->|REST API + JWT| FastAPI
    FastAPI -->|Async SQL Session| Postgres
    FastAPI -->|Extract Anomalies| LocalModel
    FastAPI -->|AI Maintenance Report| OpenRouter
```

---

## ✨ Core Features

*   **🔒 Secure Tenant Isolation:** JWT Authentication (OAuth2 password flow) with strict user-to-machine boundary checks.
*   **🏭 Machine Registry & Health Monitoring:** Real-time health status computation (`OK`, `WARNING`, `CRITICAL`) based on telemetry anomaly ratios.
*   **⚡ Large-Scale Ingestion Pipeline:** Streamed CSV ingestion utilizing `pandas` chunking to keep RAM bounded, with bulk transactional SQL insertions for maximum throughput.
*   **🤖 Advanced Anomaly Detection:** Plug-and-play architecture featuring **Isolation Forest** (default) and a statistical Z-Score fallback detector.
*   **⏳ Background Processing:** Asynchronous backend execution tracking pipeline progress (`PENDING` ➔ `PROCESSING` ➔ `COMPLETED` / `FAILED`) with telemetry counters.
*   **🔮 Generative AI Diagnostics:** Smart root-cause analysis reports via OpenRouter (`google/gemini-2.5-pro` with fallback to `gemini-2.5-flash`), degrading gracefully to a local rule-based explainer when offline.
*   **📊 Interactive Analytics Dashboard:** Beautiful Gradio UI providing live telemetry uploads, Plotly time-series visualizations with highlighted anomalies, and on-demand AI maintenance advice.
*   **🗃️ Modern Async Database Stack:** Structured around SQLAlchemy 2.0 (async engine) & Alembic migrations.

---

## 🚀 Quick Start (Docker Compose)

The easiest way to get the entire stack (API, DB, and Frontend) running.

```bash
# 1. Copy environment template and configure secrets
cp .env.example .env

# 2. Build and run containers
docker-compose up --build
```

### 📍 Service Map
- **FastAPI API & Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Gradio Interactive Web UI**: [http://localhost:7860](http://localhost:7860)

> [!NOTE]
> The database migration (`alembic upgrade head`) is executed automatically during the `api` container startup process.

---

## 💻 Local Development Setup

Follow these steps to run the application locally without Docker.

```bash
# 1. Initialize virtual environment and activate
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 2. Install package in editable mode along with dev dependencies
pip install -e ".[dev]"

# 3. Configure local environment
cp .env.example .env

# 4. Start PostgreSQL, then run migrations and launch the app
python run.py migrate
python run.py
```

---

## 🧪 Testing

The test suite runs against an in-memory SQLite database and requires zero external connections.

```bash
# Run pytest suite
pytest

# Run tests with coverage reporting
pytest --cov=app --cov-report=term-missing
```

---

## 📋 End-to-End User Journey

1. **Register & Log In:** Create an account on the **Dashboard & Auth** tab to receive a JWT session token.
2. **Register a Machine:** Add a machine (name, type, location) under your account.
3. **Upload Sensor Telemetry:** Upload a sensor CSV on the **Telemetry Upload** tab and track processing status.
4. **Interactive Analytics:** View temperature, vibration, and speed series with anomalies flagged as red crosses in **Analytics & Visuals**.
5. **Request AI Diagnosis:** Generate an AI-powered root-cause summary and actionable recommendations under **AI Assistant**.

### 📊 Expected CSV Format

The ingestion engine parses standard CSVs, auto-resolving common column aliases (e.g. `temp` for `temperature`, `rpm` for `rotational_speed`).

| timestamp | temperature | vibration | pressure | rotational_speed |
|---|---|---|---|---|
| `2026-01-01T00:00:00` | `70.2` | `0.51` | `30.1` | `1500` |

> [!TIP]
> Missing values are automatically imputed using column averages, and missing timestamps are synthesized as a monotonic, 1-second interval sequence.

---

## 📂 Project Directory Structure

```text
├── alembic/              # Async database migrations
├── src/
│   ├── app/              # FastAPI Backend Architecture
│   │   ├── api/          # Routers and JWT Dependencies
│   │   ├── core/         # Config, Database Engines, Security, Exceptions
│   │   ├── models/       # SQLAlchemy 2.0 Declarative Models
│   │   ├── repositories/ # Encapsulated Database Queries
│   │   ├── schemas/      # Pydantic v2 Serialization Schemas
│   │   └── services/     # Business Orchestration, ML Detectors & AI Services
│   ├── frontend/         # Gradio Dashboard Client
│   └── tests/            # Automated Pytest Suite
```

---

## 📄 Documentation

- 📘 **[ARCHITECTURE.md](ARCHITECTURE.md)** — Architectural design patterns, data flows, and trade-offs.
- 📙 **[WIKI.md](WIKI.md)** — Extended setup, API references, configuration tables, schema details, and production deployment guidelines.

---

## ⚖️ License

Distributed under the MIT License. See `LICENSE` for more information.
