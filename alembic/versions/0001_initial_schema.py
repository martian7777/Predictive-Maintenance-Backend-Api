"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-05

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- machines ---
    machine_status = postgresql.ENUM(
        "OK", "WARNING", "CRITICAL", name="machine_status", create_type=True
    )
    op.create_table(
        "machines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=128), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", machine_status, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_machines_name", "machines", ["name"])
    op.create_index("ix_machines_status", "machines", ["status"])
    op.create_index("ix_machines_owner_id", "machines", ["owner_id"])

    # --- sensor_telemetry ---
    op.create_table(
        "sensor_telemetry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("machine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("vibration", sa.Float(), nullable=True),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("rotational_speed", sa.Float(), nullable=True),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sensor_telemetry_timestamp", "sensor_telemetry", ["timestamp"])
    op.create_index("ix_sensor_telemetry_is_anomaly", "sensor_telemetry", ["is_anomaly"])
    op.create_index(
        "ix_telemetry_machine_timestamp", "sensor_telemetry", ["machine_id", "timestamp"]
    )
    op.create_index(
        "ix_telemetry_machine_anomaly", "sensor_telemetry", ["machine_id", "is_anomaly"]
    )

    # --- tasks ---
    task_status = postgresql.ENUM(
        "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="task_status", create_type=True
    )
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("machine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("rows_processed", sa.Integer(), nullable=False),
        sa.Column("anomalies_detected", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_machine_id", "tasks", ["machine_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("sensor_telemetry")
    op.drop_table("machines")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS machine_status")
