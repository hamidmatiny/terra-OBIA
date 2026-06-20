"""Tests for the Terra OBIA API."""

from fastapi.testclient import TestClient

from terra_api.main import create_app


def test_health_check_returns_ok() -> None:
    """Health endpoint should report service availability."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job_returns_accepted() -> None:
    """Job submission should return 202 with a placeholder job id."""
    client = TestClient(create_app())
    response = client.post(
        "/v1/jobs",
        json={
            "source_uri": "s3://example-bucket/scene.tif",
            "workflow": "forestry_stand_delineation",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert "job_id" in body
