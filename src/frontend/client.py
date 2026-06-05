"""Thin synchronous HTTP client wrapping the FastAPI backend for the Gradio UI.

Holds the bearer token in-instance so each Gradio session carries its own
authenticated client (stored in gr.State).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_V1 = os.getenv("API_V1_PREFIX", "/api/v1")


class APIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class APIClient:
    def __init__(self, base_url: str = API_BASE_URL, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.prefix = API_V1
        self.token: str | None = None
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    # ------------------------------------------------------------------ helpers
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _url(self, path: str) -> str:
        return f"{self.prefix}{path}"

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise APIError(resp.status_code, str(detail))
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    @property
    def is_authenticated(self) -> bool:
        return self.token is not None

    # ------------------------------------------------------------------ auth
    def register(self, email: str, password: str, full_name: str | None = None) -> dict:
        resp = self._client.post(
            self._url("/auth/register"),
            json={"email": email, "password": password, "full_name": full_name},
        )
        return self._handle(resp)

    def login(self, email: str, password: str) -> dict:
        resp = self._client.post(
            self._url("/auth/login"),
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = self._handle(resp)
        self.token = data["access_token"]
        return data

    def me(self) -> dict:
        return self._handle(self._client.get(self._url("/auth/me"), headers=self._headers()))

    def logout(self) -> None:
        self.token = None

    # ------------------------------------------------------------------ machines
    def list_machines(self) -> list[dict]:
        return self._handle(
            self._client.get(self._url("/machines"), headers=self._headers())
        )

    def create_machine(self, name: str, type_: str, location: str | None = None) -> dict:
        return self._handle(
            self._client.post(
                self._url("/machines"),
                json={"name": name, "type": type_, "location": location},
                headers=self._headers(),
            )
        )

    def machine_summary(self, machine_id: str) -> dict:
        return self._handle(
            self._client.get(
                self._url(f"/machines/{machine_id}/summary"), headers=self._headers()
            )
        )

    # ------------------------------------------------------------------ telemetry
    def upload_csv(self, machine_id: str, file_path: str) -> dict:
        with open(file_path, "rb") as fh:
            files = {"file": (os.path.basename(file_path), fh, "text/csv")}
            resp = self._client.post(
                self._url(f"/telemetry/upload/{machine_id}"),
                files=files,
                headers=self._headers(),
            )
        return self._handle(resp)

    def get_task(self, task_id: str) -> dict:
        return self._handle(
            self._client.get(
                self._url(f"/telemetry/tasks/{task_id}"), headers=self._headers()
            )
        )

    def get_series(self, machine_id: str, limit: int = 5000) -> dict:
        return self._handle(
            self._client.get(
                self._url(f"/telemetry/machines/{machine_id}/series"),
                params={"limit": limit},
                headers=self._headers(),
            )
        )

    # ------------------------------------------------------------------ ai
    def explain(self, machine_id: str, window: int = 500) -> dict:
        return self._handle(
            self._client.get(
                self._url(f"/ai/explain/{machine_id}"),
                params={"window": window},
                headers=self._headers(),
            )
        )
