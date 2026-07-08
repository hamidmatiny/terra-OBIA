"""Integration: terra-obia-etl trained model → terra-OBIA classifier prediction."""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from terra_core.classification import ClassificationConfig, StandDelineationClassifier
from terra_core.classification.registry import load_model_artifact
from terra_core.classification.scripts.register_etl_model import (
    DEFAULT_VARIANT,
    default_etl_model_dir,
    register_etl_model,
    validate_artifact,
)


def _candidate_etl_model_dirs() -> list[Path]:
    """Return candidate paths for the committed GeoNB balanced model."""
    candidates: list[Path] = []
    env = os.environ.get("TERRA_ETL_MODEL_DIR")
    if env:
        candidates.append(Path(env).expanduser().resolve())
    candidates.append(default_etl_model_dir(DEFAULT_VARIANT))
    # CI checkout path used by the terra-OBIA workflow
    candidates.append((Path.cwd() / "terra-obia-etl" / "models" / DEFAULT_VARIANT).resolve())
    return candidates


def resolve_etl_model_dir() -> Path:
    """Find the real ETL model artifact or skip when unavailable."""
    tried: list[str] = []
    for candidate in _candidate_etl_model_dirs():
        tried.append(str(candidate))
        if candidate.is_dir() and (candidate / "metadata.json").exists():
            return candidate
    pytest.skip(
        "terra-obia-etl model artifact not found. "
        f"Tried: {tried}. "
        "Checkout terra-obia-etl as a sibling or set TERRA_ETL_MODEL_DIR, "
        "then run: poetry run terra-register-etl-model"
    )


@pytest.fixture
def geonb_feature_objects() -> gpd.GeoDataFrame:
    """Segment-like objects with the GeoNB inventory feature schema."""
    return gpd.GeoDataFrame(
        {
            "object_id": [1, 2, 3],
            "area_m2": [25000.0, 18000.0, 5000.0],
            "perimeter_m": [800.0, 600.0, 300.0],
            "compactness": [0.5, 0.6, 0.7],
            "l1_ds": [2.0, 1.0, 0.0],
            "l1_sc": [3.0, 2.0, 0.0],
            "l1_vs": [2.0, 1.0, 0.0],
            "l1_pstock": [0.0, 0.0, 0.0],
            "lc_code": [0.0, 0.0, 1.0],
            "wri_code": [0.0, 0.0, 0.0],
            "spvc": [0.0, 0.0, 0.0],
        },
        geometry=[
            box(0, 0, 100, 100),
            box(110, 0, 210, 100),
            box(0, 110, 100, 210),
        ],
        crs="EPSG:32619",
    )


def test_register_etl_model_makes_artifact_available(
    tmp_path: Path,
    geonb_feature_objects: gpd.GeoDataFrame,
) -> None:
    """One-command handoff should register the real ETL model for OBIA inference."""
    source = resolve_etl_model_dir()
    metadata = validate_artifact(source)
    assert metadata["model_id"] == "stand_20260621T181026Z_23d8ae05"

    models_dir = tmp_path / "models"
    registered = register_etl_model(source, models_dir=models_dir, mode="copy")
    assert registered.exists()
    assert (registered / "cover_type_model.joblib").exists()

    # Registry-style discovery: metadata.json under models/
    discovered = list(models_dir.rglob("metadata.json"))
    assert len(discovered) == 1
    discovered_meta = json.loads(discovered[0].read_text(encoding="utf-8"))
    assert discovered_meta["model_id"] == metadata["model_id"]

    classifier = StandDelineationClassifier(
        ClassificationConfig(model_artifact_path=registered),
    )
    result = classifier.classify_objects(geonb_feature_objects)

    assert result.model_version == metadata["model_id"]
    assert "cover_type" in result.objects.columns
    assert "canopy_closure_class" in result.objects.columns
    assert "confidence" in result.objects.columns
    assert len(result.objects) == 3
    assert result.objects["cover_type"].notna().all()
    assert result.objects["canopy_closure_class"].notna().all()
    assert (result.objects["confidence"] > 0).all()
    assert set(result.objects["canopy_closure_class"]).issubset(
        {"open", "sparse", "moderate", "dense"}
    )


def test_load_real_etl_balanced_model_directly(geonb_feature_objects: gpd.GeoDataFrame) -> None:
    """Loading the committed ETL artifact without copying still predicts attributes."""
    source = resolve_etl_model_dir()
    artifact = load_model_artifact(source)
    assert artifact.metadata.model_id == "stand_20260621T181026Z_23d8ae05"
    assert "l1_ds" in artifact.metadata.feature_columns

    classifier = StandDelineationClassifier(
        ClassificationConfig(model_artifact_path=source),
    )
    result = classifier.classify_objects(geonb_feature_objects)
    assert list(result.objects["cover_type"])  # non-empty predictions
    assert list(result.objects["canopy_closure_class"])
