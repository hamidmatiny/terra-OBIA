"""Tests for the Terra OBIA API."""

from fastapi.testclient import TestClient

from terra_api.config import settings
from terra_api.main import create_app


def test_health_check_returns_ok() -> None:
    """Health endpoint should report service availability."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job_requires_model_id(monkeypatch) -> None:
    """Job submission should validate required fields."""
    monkeypatch.setattr(settings, "api_key", None)
    client = TestClient(create_app())
    response = client.post(
        "/v1/jobs",
        json={"source_uri": "/tmp/test.tif"},
    )
    assert response.status_code == 422
