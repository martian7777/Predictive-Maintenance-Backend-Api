"""Machine endpoint tests, including ownership isolation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_and_get_machine(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/api/v1/machines",
        json={"name": "Motor-A", "type": "motor", "location": "Line 1"},
    )
    assert resp.status_code == 201
    mid = resp.json()["id"]

    got = await auth_client.get(f"/api/v1/machines/{mid}")
    assert got.status_code == 200
    assert got.json()["name"] == "Motor-A"
    assert got.json()["status"] == "OK"


async def test_list_machines(auth_client: AsyncClient):
    for i in range(3):
        await auth_client.post("/api/v1/machines", json={"name": f"M{i}", "type": "pump"})
    resp = await auth_client.get("/api/v1/machines")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_update_machine(auth_client: AsyncClient, machine_id: str):
    resp = await auth_client.patch(f"/api/v1/machines/{machine_id}", json={"status": "WARNING"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "WARNING"


async def test_delete_machine(auth_client: AsyncClient, machine_id: str):
    resp = await auth_client.delete(f"/api/v1/machines/{machine_id}")
    assert resp.status_code == 204
    missing = await auth_client.get(f"/api/v1/machines/{machine_id}")
    assert missing.status_code == 404


async def test_machine_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/machines")
    assert resp.status_code == 401


async def test_machine_summary_empty(auth_client: AsyncClient, machine_id: str):
    resp = await auth_client.get(f"/api/v1/machines/{machine_id}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["telemetry_count"] == 0
    assert body["anomaly_count"] == 0


async def test_ownership_isolation(client: AsyncClient):
    # User A creates a machine.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123"},
    )
    login_a = await client.post(
        "/api/v1/auth/login", data={"username": "a@example.com", "password": "password123"}
    )
    token_a = login_a.json()["access_token"]
    created = await client.post(
        "/api/v1/machines",
        json={"name": "Secret", "type": "pump"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    mid = created.json()["id"]

    # User B must not see or fetch it.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "password": "password123"},
    )
    login_b = await client.post(
        "/api/v1/auth/login", data={"username": "b@example.com", "password": "password123"}
    )
    token_b = login_b.json()["access_token"]
    resp = await client.get(
        f"/api/v1/machines/{mid}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404
