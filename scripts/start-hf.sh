#!/bin/bash
set -e

# Run alembic migrations
echo "Running database migrations..."
alembic upgrade head

# Start FastAPI backend in the background on port 8000
echo "Starting FastAPI backend..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait for backend to be ready
echo "Waiting for backend to start..."
until curl -s http://localhost:8000/api/v1/auth/me > /dev/null || [ $? -ne 7 ]; do
  sleep 1
done
echo "Backend is up!"

# Start Gradio frontend in the foreground on port 7860
echo "Starting Gradio frontend..."
python -m frontend.app
