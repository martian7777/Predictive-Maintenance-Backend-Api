# Operations & Usage Wiki

Welcome to the operations wiki. This guide covers setup, database configuration, full API endpoints, Gradio client instructions, testing, troubleshooting, and production deployment parameters.

---

## 📋 Table of Contents

1. [⚙️ Prerequisites](#1-prerequisites)
2. [🎛️ System Configuration](#2-configuration)
3. [🐳 Containerized Deployment (Docker)](#3-running-with-docker)
4. [🛠️ Native Local Setup](#4-running-locally)
5. [🗄️ Database Migrations](#5-database--migrations)
6. [🗃️ Database Schema](#6-database-schema)
7. [🔌 REST API Reference](#7-api-reference)
8. [📊 Using the Gradio UI](#8-using-the-gradio-ui)
9. [📈 Ingestion Parameters & CSV Formats](#9-csv-format--ingestion)
10. [🌲 Anomaly Detection Configuration](#10-anomaly-detection)
11. [🤖 GenAI OpenRouter Setup](#11-ai-explanations-openrouter)
12. [🧪 Testing Instructions](#12-testing)
13. [🩺 Troubleshooting Guide](#13-troubleshooting)
14. [🚀 Production Checklist](#14-production-deployment)

---

## 1. Prerequisites

Before installing, ensure your machine satisfies the following hardware and software versions:
- **Python**: Version `3.11+`
- **PostgreSQL**: Version `14` or newer (PG 16 recommended)
- **Docker & Compose**: Optional, but recommended for zero-configuration startup.
- **OpenRouter API Key**: Optional. Required to output LLM-backed diagnostics; defaults to a rule-based engine if empty.

---

## 2. Configuration

All application configurations are driven by local environment variables. They are loaded and validated by Pydantic Settings at startup (`app/core/config.py`).

To initialize configuration:
```bash
cp .env.example .env
```

### ⚙️ Available Settings

| Variable | Default Value | Purpose / Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | Core environment context: `development`, `testing`, or `production`. |
| `DEBUG` | `true` | Enables verbose debug logging and raw SQL command echoing. |
| `API_V1_PREFIX` | `/api/v1` | Root context prefix for all API routers. |
| `API_PORT` | `8000` | Port assigned to the FastAPI server. |
| `FRONTEND_PORT` | `7860` | Port assigned to the Gradio web client. |
| `API_BASE_URL` | `http://localhost:8000` | Address used by the frontend client to communicate with the API. |
| `POSTGRES_HOST` | `localhost` | PostgreSQL hostname. |
| `POSTGRES_PORT` | `5432` | PostgreSQL standard port. |
| `POSTGRES_USER` | `postgres` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL password. |
| `POSTGRES_DB` | `predictive_db` | Target database name. |
| `DATABASE_URL` | *(None)* | Overrides connection parts with a direct, custom async connection string. |
| `JWT_SECRET_KEY` | *(Required)* | Asymmetric HMAC key for signature validation. Change this in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `60` | Expiration time of generated bearer tokens. |
| `OPENROUTER_API_KEY` | *(None)* | OpenRouter credentials. If omitted, the mock explainer starts. |
| `OPENROUTER_MODEL` | `google/gemini-2.5-pro` | Primary LLM model used for reports. |
| `OPENROUTER_FALLBACK_MODEL` | `google/gemini-2.5-flash` | Fallback model used on network or quota failure. |
| `CSV_CHUNK_SIZE` | `50000` | Iteration size for chunked pandas streams. |
| `ISOLATION_FOREST_CONTAMINATION`| `0.02` | Expected percentage of anomalies in raw feeds. |
| `ISOLATION_FOREST_N_ESTIMATORS` | `100` | Number of decision trees to spawn in the Isolation Forest. |
| `MODEL_DIR` | `./models` | Directory path where trained `.joblib` model binaries are saved. |

> [!TIP]
> You can quickly generate a secure, 64-character JWT secret key with this command:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(64))"
> ```

---

## 3. Running with Docker

Deploy a production-like environment with a single command:

```bash
docker-compose up --build
```

### 📦 Services Manifest
- **`db`** (Port `5432`): Starts PostgreSQL 16. Uses a persistent named volume (`pgdata`) to protect sensor data across restarts.
- **`api`** (Port `8000`): Runs database migrations automatically (`alembic upgrade head`) and launches `uvicorn`.
- **`frontend`** (Port `7860`): Launches the Gradio application inside the Compose network.

> [!IMPORTANT]
> To execute tests inside a containerized runtime, execute:
> ```bash
> docker-compose run --rm api pytest -v
> ```

To tear down services while preserving databases, use `docker-compose down`. Use the `-v` flag if you want to completely purge databases and start fresh: `docker-compose down -v`.

---

## 4. Running Locally

Follow these instructions to run the application components natively.

### 🐍 Virtual Environment Setup
```bash
# Initialize
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Linux / macOS Bash)
source .venv/bin/activate

# Install development and testing dependencies
pip install -e ".[dev]"
```

### 🏃 Start Services
Ensure you have a PostgreSQL database instance running (Docker makes this easy: `docker-compose up -d db`), then run:

```bash
# Run database migrations
python run.py migrate

# Start backend and frontend services in parallel
python run.py
```

The script `run.py` accepts task flags. To isolate workloads, run:
- `python run.py api` (Starts FastAPI backend only)
- `python run.py frontend` (Starts Gradio client only)
- `python run.py migrate` (Executes Alembic migrations only)

---

## 5. Database & Migrations

Database operations are managed via async Alembic. Settings are loaded programmatically, ignoring the static connection configuration inside `alembic.ini`.

```bash
# Bring the database schema up to the latest revision
alembic upgrade head

# Roll back the database schema by one revision
alembic downgrade -1

# Show the active schema version hash
alembic current

# Output history logs of all migrations
alembic history

# Generate a new migration file after modifying models
alembic revision --autogenerate -m "describe changes here"
```

> [!NOTE]
> Custom migrations are auto-formatted upon generation using a pre-configured Ruff post-write hook.

---

## 6. Database Schema

The database relies on 4 core tables to manage tenants, physical assets, telemetry feeds, and ingestion logs.

```mermaid
erDiagram
    USERS ||--o{ MACHINES : "manages"
    MACHINES ||--o{ SENSOR_TELEMETRY : "records"
    MACHINES ||--o{ INGESTION_TASKS : "runs"

    USERS {
        uuid id PK "Primary key"
        varchar email UK "Unique login identifier"
        varchar hashed_password "Bcrypt encrypted hash"
        varchar full_name "User full name"
        boolean is_active "Status flag"
        boolean is_superuser "Admin privilege flag"
        timestamp created_at "Record creation time"
        timestamp updated_at "Record modification time"
    }

    MACHINES {
        uuid id PK "Primary key"
        uuid owner_id FK "References USERS.id"
        varchar name "Machine identity label"
        varchar type "Machine classification (e.g. pump)"
        varchar location "Installation location"
        varchar status "OK | WARNING | CRITICAL"
        timestamp created_at "Record creation time"
        timestamp updated_at "Record modification time"
    }

    SENSOR_TELEMETRY {
        uuid id PK "Primary key"
        uuid machine_id FK "References MACHINES.id"
        timestamp timestamp INDEX "Measurement time"
        float temperature "Sensor metric"
        float vibration "Sensor metric"
        float pressure "Sensor metric"
        float rotational_speed "Sensor metric"
        float anomaly_score "Computed score [0, 1]"
        boolean is_anomaly INDEX "Scored outlier flag"
    }

    INGESTION_TASKS {
        uuid id PK "Primary key"
        uuid machine_id FK "References MACHINES.id"
        varchar status "PENDING | PROCESSING | COMPLETED | FAILED"
        varchar file_name "Uploaded CSV file name"
        integer rows_processed "Processed telemetry rows count"
        integer anomalies_detected "Outlier rows count"
        text error_message "Failure details (if any)"
        timestamp created_at "Record creation time"
        timestamp updated_at "Record modification time"
    }
```

### ⚡ Optimization Indexes
- **`sensor_telemetry(machine_id, timestamp)`**: Accelerates historical timeline extraction and visual rendering.
- **`sensor_telemetry(machine_id, is_anomaly)`**: Speeds up filtering operations on isolated anomaly events.

---

## 7. REST API Reference

Explore the full HTTP REST contract. The active Swagger definition resides at `http://localhost:8000/docs`. All routes are prefixed with `/api/v1`.

### 🔐 Auth Endpoint
| Method | Endpoint | Authentication | Details |
|:---:|---|:---:|---|
| **`POST`** | `/auth/register` | None | Create a user. Payload: `{email, password, full_name}` |
| **`POST`** | `/auth/login` | None | Classic OAuth2 login. Form body: `username`, `password`. |
| **`GET`** | `/auth/me` | ✅ Bearer | Returns the profile model of the authenticated user. |

### 🏭 Machine Registry
| Method | Endpoint | Authentication | Details |
|:---:|---|:---:|---|
| **`POST`** | `/machines` | ✅ Bearer | Create a new asset. Payload: `{name, type, location}` |
| **`GET`** | `/machines` | ✅ Bearer | Paginated list of owned assets. Parameters: `skip`, `limit` |
| **`GET`** | `/machines/{id}` | ✅ Bearer | Extract details for a specific machine. |
| **`PATCH`**| `/machines/{id}` | ✅ Bearer | Modify fields or status markers. |
| **`DELETE`**| `/machines/{id}` | ✅ Bearer | Delete asset (cascades telemetry and tasks). |
| **`GET`** | `/machines/{id}/summary` | ✅ Bearer | Combines machine metadata with computed anomaly statistics. |

### 📈 Telemetry Ingestion
| Method | Endpoint | Authentication | Details |
|:---:|---|:---:|---|
| **`POST`** | `/telemetry/upload/{machine_id}` | ✅ Bearer | Stream multipart CSV file ➔ Returns `{task_id}` |
| **`GET`** | `/telemetry/tasks/{task_id}` | ✅ Bearer | Read the execution details of an ingestion task. |
| **`GET`** | `/telemetry/machines/{id}/tasks` | ✅ Bearer | Fetch ingestion task history for an asset. |
| **`GET`** | `/telemetry/machines/{id}/series`| ✅ Bearer | Get array lists of recent sensor readings. |
| **`GET`** | `/telemetry/machines/{id}/anomalies`| ✅ Bearer | Extract anomalous records only. |

### 🤖 AI Reports
| Method | Endpoint | Authentication | Details |
|:---:|---|:---:|---|
| **`GET`** | `/ai/explain/{machine_id}?window=N` | ✅ Bearer | Fetch AI-driven diagnostic report for the last N readings. |

### 🩺 Health & System
| Method | Endpoint | Authentication | Details |
|:---:|---|:---:|---|
| **`GET`** | `/health` | None | Checks database status and displays AI enablement status. |
| **`GET`** | `/` | None | Returns backend service metadata and versions. |

---

## 8. Using the Gradio UI

Start the Gradio service (Port `7860`) and navigate through the structured tabs:

1. **Dashboard & Auth**:
   - Register or log into your account.
   - View your registered machines in a grid showing live status labels (`OK`, `WARNING`, `CRITICAL`).
   - Create new machine entries.
2. **Telemetry Upload**:
   - Select an asset from the dropdown list.
   - Attach a `.csv` telemetry file and submit.
   - Monitor the ingestion progress bar, which polls the task status in the background.
3. **Analytics & Visuals**:
   - Load dynamic Plotly graphs plotting temperature, pressure, speed, and vibration.
   - **Anomalies are highlighted as red "X" markers** directly on the lines.
   - Review general statistics (min, max, mean) for each sensor.
4. **AI Assistant**:
   - Request Gemini model analysis for the recent telemetry sequence.
   - Review anomaly root cause summaries, technical explanations, and recommended operations.

---

## 9. Ingestion Parameters & CSV Formats

Uploaded CSV files must contain at least one sensor column. The headers are case-insensitive and automatically resolve common aliases:

| Canonical Header | Valid Column Name Aliases |
|---|---|
| `timestamp` | `time`, `datetime`, `date` |
| `temperature` | `temp`, `celcius` |
| `vibration` | `vib`, `vibration_amplitude` |
| `pressure` | `psi`, `bar`, `pressure_v` |
| `rotational_speed` | `rpm`, `speed` |

### 🛡️ Data Cleaning & Processing Pipeline
1. **Missing Data**: Rows with empty values are filled using mean values calculated from the file data.
2. **Missing Timestamps**: If timestamps are missing or invalid, the ingestion pipeline generates a continuous sequence starting from the last known date, incrementing by 1 second.
3. **Status Recalculation**: Once an upload is complete, the machine health is updated based on the percentage of anomalies:
   - **`CRITICAL`**: Anomaly ratio is **`≥ 10%`**.
   - **`WARNING`**: Anomaly ratio is **`between 0.1% and 10%`**, or any single anomaly is found.
   - **`OK`**: Zero anomalies are detected.

---

## 10. Anomaly Detection

The ML core uses **Isolation Forest** algorithms from `scikit-learn` inside `app/services/anomaly_service.py`. You can adjust model parameters via your `.env` file:
- `ISOLATION_FOREST_CONTAMINATION`: The expected outlier ratio in the dataset.
- `ISOLATION_FOREST_N_ESTIMATORS`: The size of the forest.

> [!NOTE]
> The anomaly detection pipeline uses standard Python interfaces. If you want to use deep learning models (like PyTorch Autoencoders), implement the `AnomalyDetector` class protocol and update `get_default_detector()` in the service layer.

---

## 11. AI Explanations (OpenRouter)

Add your `OPENROUTER_API_KEY` to the `.env` file to enable AI-powered maintenance diagnostics.
- The service uses the official OpenAI SDK configured to target the OpenRouter base URL.
- Structured output is enforced using JSON Schemas.
- If OpenRouter fails (e.g. rate limits or API outage), the service attempts a fallback to `OPENROUTER_FALLBACK_MODEL`.
- If no key is configured, a local rules engine analyzes sensor deviations to output deterministic diagnostic reports.

---

## 12. Testing

The test suite runs inside an isolated, mock environment:

```bash
# Run all unit and integration tests
pytest

# Run tests and output missing coverage lines
pytest --cov=app --cov-report=term-missing
```

### 🔬 Test Strategy
- **SQLite Engine**: An in-memory SQLite database is used instead of PostgreSQL.
- **Mock AI Explainer**: Tests run without internet access, verifying the local rules engine.
- **Task Mocking**: The background worker session is configured to run synchronously within the testing process, allowing seamless validation of the upload-to-ingest lifecycle.

---

## 13. Troubleshooting

Use this guide to diagnose and resolve common issues:

| Problem | Potential Cause | Fix / Solution |
|---|---|---|
| **`401: Could not validate credentials`** | Missing or expired token. | Log in again via the Auth tab to refresh the JWT token. |
| **`404: Machine not found`** | Wrong machine ID, or the machine belongs to another user. | Verify the ID. The API hides other users' assets with `404` errors to prevent enumeration. |
| **Task stuck in `PENDING` status** | The API server is unable to dispatch background tasks. | Check the API logs to verify the database connection is healthy. |
| **`is_mock` is `true` in AI reports** | API key is missing or the external API call failed. | Check that `OPENROUTER_API_KEY` is set and valid, and review system logs for API errors. |
| **Analytics charts are empty** | Ingestion task failed, or no telemetry has been uploaded yet. | Check the machine's task history and inspect the `error_message` for details. |
| **Alembic fails to connect** | The database URL is incorrect, or PostgreSQL is not running. | Verify `POSTGRES_HOST` / `DATABASE_URL` in `.env` and ensure the database container is healthy. |
| **SQLite errors in local development** | The backend is attempting to connect to SQLite. | The main application requires PostgreSQL. SQLite is only supported for testing. |

---

## 14. Production Deployment

### 📋 Checklist

- [ ] Set `ENVIRONMENT=production` and `DEBUG=false` in the production `.env` file.
- [ ] Generate a secure, high-entropy `JWT_SECRET_KEY`.
- [ ] Configure `allow_origins` in `app/main.py` to allow only trusted frontend domains.
- [ ] Set up database backups for your PostgreSQL instance, and run `alembic upgrade head` in your deployment pipeline.
- [ ] Run backend servers using production-grade WSGI/ASGI servers (like Uvicorn/Gunicorn) behind a reverse proxy (e.g. Nginx, Cloudflare) with TLS enabled.
- [ ] If running multiple backend containers, configure shared storage (e.g. S3, shared volume) for `MODEL_DIR` so all replicas can access serialized models.
- [ ] Transition task processing to an external task worker (like Celery/Arq with Redis) for improved scaling and retry capabilities.

### 🚀 Production Startup Command

```bash
ENVIRONMENT=production DEBUG=false \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

> [!WARNING]
> By default, FastAPI `BackgroundTasks` execute inside the active container process. When scaling to multiple Uvicorn workers, task state is restricted to the worker that received the upload. Deploy an external task queue (like Arq) to share ingestion workloads across all instances.
