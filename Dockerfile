FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create user 1000 for Hugging Face compatibility
RUN useradd -m -u 1000 user
RUN chown -R user:user /home/user

# Switch to user 1000
USER user

# Copy requirements/files
COPY --chown=user:user pyproject.toml README.md ./
COPY --chown=user:user src ./src
COPY --chown=user:user alembic.ini ./
COPY --chown=user:user alembic ./alembic

# Install the project and dependencies
RUN pip install --user --upgrade pip && pip install --user .

# Copy and setup startup script
COPY --chown=user:user scripts/start-hf.sh ./start-hf.sh
RUN chmod +x ./start-hf.sh

# Expose Gradio port
EXPOSE 7860

# Default environment variables for the self-contained deployment
ENV ENVIRONMENT=production \
    DATABASE_URL=sqlite+aiosqlite:////home/user/app/predictive_maintenance.db \
    API_BASE_URL=http://localhost:8000 \
    FRONTEND_PORT=7860 \
    FRONTEND_HOST=0.0.0.0 \
    JWT_SECRET_KEY=hf-space-random-secret-key-12345

CMD ["./start-hf.sh"]
