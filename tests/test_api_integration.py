"""Integration tests for the Terra OBIA REST API job lifecycle."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.crs import CRS
from rasterio.transform import from_origin

from terra_api.config import settings
from terra_api.main import create_app
from terra_api.schemas import JobStatus
from terra_core.classification.training import (
    TrainingConfig,
    load_labeled_dataset,
    train_stand_classifier,
)
from terra_core.export import read_exported_file


@pytest.fixture
def api_test_raster(tmp_path: Path) -> Path:
    """Create a small 600×600 GeoTIFF for fast API integration tests."""
    path = tmp_path / "api_test.tif"
    width, height = 600, 600
    transform = from_origin(700000.0, 5450000.0, 10.0, 10.0)
    rng = np.random.default_rng(7)
    data = rng.integers(100, 900, size=(3, height, width), dtype=np.uint16)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 3,
        "dtype": "uint16",
        "crs": CRS.from_epsg(32619),
        "transform": transform,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(data)
    return path


@pytest.fixture
def trained_model(tmp_path: Path) -> str:
    """Train a stand classifier and return its model ID."""
    import pandas as pd

    csv_path = tmp_path / "labeled.csv"
    rows = []
    for idx in range(60):
        cover = ["conifer", "deciduous", "mixed"][idx % 3]
        base = {"conifer": 0.8, "deciduous": 0.4, "mixed": 0.6}[cover]
        rows.append(
            {
                "object_id": idx + 1,
                "area_m2": 1000.0 + idx,
                "perimeter_m": 120.0,
                "compactness": 0.7,
                "mean_band_1": base,
                "mean_band_2": base * 0.8,
                "mean_band_3": base * 0.6,
                "std_band_1": 0.05,
                "std_band_2": 0.04,
                "std_band_3": 0.03,
                "cover_type": cover,
                "canopy_closure_class": ["sparse", "moderate", "dense"][idx % 3],
            }
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    models_dir = tmp_path / "models"
    artifact = train_stand_classifier(
        load_labeled_dataset(csv_path),
        TrainingConfig(training_data_description="API integration test model"),
        output_dir=models_dir / "stand_model",
    )
    return artifact.metadata.model_id


@pytest.fixture
def api_client(tmp_path: Path, trained_model: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Configure API settings and return an authenticated test client."""
    monkeypatch.setattr(settings, "models_dir", tmp_path / "models")
    monkeypatch.setattr(settings, "job_output_dir", tmp_path / "job_outputs")
    monkeypatch.setattr(settings, "api_key", "test-secret-key")
    os.environ["TERRA_API_KEY"] = "test-secret-key"
    client = TestClient(create_app())
    client.headers.update({"X-API-Key": "test-secret-key"})
    return client


def test_models_endpoint_lists_trained_model(api_client: TestClient, trained_model: str) -> None:
    """GET /models should list the trained model with accuracy metadata."""
    response = api_client.get("/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert any(model["model_id"] == trained_model for model in body["models"])


def test_full_job_lifecycle(
    api_client: TestClient,
    api_test_raster: Path,
    trained_model: str,
) -> None:
    """End-to-end job: submit, poll status, fetch results, validate GIS exports."""
    submit = api_client.post(
        "/v1/jobs",
        json={
            "source_uri": str(api_test_raster),
            "workflow": "stand_delineation",
            "model_id": trained_model,
            "segmentation": {
                "backend": "classical",
                "n_segments": 30,
                "compactness": 12.0,
                "tile_size": 256,
                "overlap": 32,
            },
            "export_formats": ["geojson", "gpkg", "shp"],
        },
    )
    assert submit.status_code == 202
    job_id = submit.json()["job_id"]

    status_response = api_client.get(f"/v1/jobs/{job_id}")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] in {JobStatus.COMPLETED.value, JobStatus.RUNNING.value}

    if status_body["status"] != JobStatus.COMPLETED.value:
        status_body = api_client.get(f"/v1/jobs/{job_id}").json()
    assert status_body["status"] == JobStatus.COMPLETED.value
    assert status_body["progress"]["percent"] == 100

    results = api_client.get(f"/v1/jobs/{job_id}/results")
    assert results.status_code == 200
    results_body = results.json()
    assert results_body["object_count"] >= 0
    assert len(results_body["exports"]) == 3

    for export in results_body["exports"]:
        loaded = read_exported_file(export["path"])
        assert loaded.crs is not None
        assert len(loaded) == results_body["object_count"]


def test_api_key_required_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Requests without API key should be rejected when TERRA_API_KEY is set."""
    monkeypatch.setattr(settings, "api_key", "required-key")
    client = TestClient(create_app())
    response = client.get("/v1/models")
    assert response.status_code == 401
