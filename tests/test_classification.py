"""Tests for stand delineation classification, training, and evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

from terra_core.classification import (
    ClassificationConfig,
    StandDelineationClassifier,
    compute_object_classification_metrics,
    compute_polygon_iou,
    create_classifier,
    load_labeled_dataset,
    load_model_artifact,
    train_stand_classifier,
    write_accuracy_report_markdown,
)
from terra_core.classification.training import TrainingConfig


def test_train_and_save_model_artifact(synthetic_labeled_csv: Path, tmp_path: Path) -> None:
    """Training should persist a versioned artifact with metadata."""
    output_dir = tmp_path / "models" / "stand_v1"
    config = TrainingConfig(training_data_description="Synthetic NB stand samples")
    artifact = train_stand_classifier(
        load_labeled_dataset(synthetic_labeled_csv),
        config,
        output_dir=output_dir,
    )

    assert (output_dir / "metadata.json").exists()
    assert (output_dir / "cover_type_model.joblib").exists()
    assert (output_dir / "canopy_closure_model.joblib").exists()

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["model_id"] == artifact.metadata.model_id
    assert metadata["workflow"] == "stand_delineation"
    assert "overall_accuracy" in metadata["validation_metrics"]


def test_load_model_round_trip(synthetic_labeled_csv: Path, tmp_path: Path) -> None:
    """Saved artifacts should reload with identical metadata."""
    output_dir = tmp_path / "model"
    train_stand_classifier(
        load_labeled_dataset(synthetic_labeled_csv),
        TrainingConfig(training_data_description="Round-trip test"),
        output_dir=output_dir,
    )
    loaded = load_model_artifact(output_dir)
    assert loaded.metadata.workflow == "stand_delineation"
    assert loaded.metadata.feature_columns


def test_stand_classifier_predicts_attributes(
    synthetic_labeled_csv: Path,
    synthetic_segmented_objects: gpd.GeoDataFrame,
    tmp_path: Path,
) -> None:
    """Stand classifier should add cover type, canopy closure, and confidence."""
    output_dir = tmp_path / "model"
    train_stand_classifier(
        load_labeled_dataset(synthetic_labeled_csv),
        TrainingConfig(training_data_description="Prediction test"),
        output_dir=output_dir,
    )
    classifier = StandDelineationClassifier(
        ClassificationConfig(model_artifact_path=output_dir),
    )
    result = classifier.classify_objects(synthetic_segmented_objects)

    assert "cover_type" in result.objects.columns
    assert "canopy_closure_class" in result.objects.columns
    assert "confidence" in result.objects.columns
    assert len(result.objects) == 3
    assert result.model_version


def test_create_classifier_factory(
    synthetic_labeled_csv: Path,
    synthetic_segmented_objects: gpd.GeoDataFrame,
    tmp_path: Path,
) -> None:
    """Factory should instantiate stand delineation workflow."""
    output_dir = tmp_path / "model"
    train_stand_classifier(
        load_labeled_dataset(synthetic_labeled_csv),
        TrainingConfig(training_data_description="Factory test"),
        output_dir=output_dir,
    )
    classifier = create_classifier(ClassificationConfig(model_artifact_path=output_dir))
    result = classifier.classify_objects(synthetic_segmented_objects)
    assert result.workflow == "stand_delineation"


def test_accuracy_reporting_metrics(synthetic_labeled_csv: Path) -> None:
    """Accuracy module should compute object-level metrics."""
    labeled = load_labeled_dataset(synthetic_labeled_csv)
    assert isinstance(labeled, pd.DataFrame)
    y_cover = labeled["cover_type"].astype(str).to_numpy()
    y_canopy = labeled["canopy_closure_class"].astype(str).to_numpy()
    report = compute_object_classification_metrics(y_cover, y_cover, y_canopy, y_canopy)
    assert report.overall_accuracy == pytest.approx(1.0)
    assert "conifer" in report.cover_type_metrics


def test_polygon_iou_computation(
    synthetic_segmented_objects: gpd.GeoDataFrame,
    synthetic_reference_polygons: gpd.GeoDataFrame,
) -> None:
    """IoU should be high when predicted labels align with reference geometry."""
    predicted = synthetic_segmented_objects.copy()
    predicted["cover_type"] = ["conifer", "deciduous", "mixed"]
    mean_iou, per_class = compute_polygon_iou(predicted, synthetic_reference_polygons)
    assert mean_iou > 0.5
    assert "conifer" in per_class


def test_write_accuracy_report_markdown(tmp_path: Path) -> None:
    """Markdown report writer should produce a readable sales/audit artifact."""
    from terra_core.classification.models import AccuracyReport

    report = AccuracyReport(
        overall_accuracy=0.87,
        cover_type_metrics={
            "conifer": {"precision": 0.9, "recall": 0.85, "f1-score": 0.87, "support": 20},
        },
        canopy_closure_metrics={
            "dense": {"precision": 0.88, "recall": 0.86, "f1-score": 0.87, "support": 15},
        },
        mean_iou=0.82,
        per_class_iou={"conifer": 0.84, "deciduous": 0.80},
        support={"conifer": 20},
    )
    path = write_accuracy_report_markdown(
        report,
        tmp_path / "report.md",
        model_id="stand_test_001",
        training_data_description="Synthetic validation set",
    )
    content = path.read_text(encoding="utf-8")
    assert "Overall accuracy" in content
    assert "Mean polygon IoU" in content
    assert "stand_test_001" in content
