"""Training pipeline for stand delineation gradient boosting classifiers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight

from terra_core.classification.evaluation import compute_object_classification_metrics
from terra_core.classification.features import labeled_frame_to_features
from terra_core.classification.models import ModelMetadata
from terra_core.classification.registry import (
    StandClassifierArtifact,
    load_model_artifact,
    new_model_id,
    save_model_artifact,
)

logger = logging.getLogger("terra_core.classification")


@dataclass(frozen=True)
class TrainingConfig:
    """Configuration for stand delineation model training."""

    training_data_description: str
    test_size: float = 0.25
    random_state: int = 42
    n_estimators: int = 100
    max_depth: int = 3
    verbose: int = 1
    class_weight: str | None = None
    cover_type_column: str = "cover_type"
    canopy_closure_column: str = "canopy_closure_class"


def load_labeled_dataset(path: Path | str) -> pd.DataFrame | gpd.GeoDataFrame:
    """Load labeled training data from CSV or GeoPackage.

    Expected CRS/resolution assumptions:
        - GeoPackage rows include stand polygon geometry in a projected CRS.
        - CSV rows contain per-object feature columns without geometry.

    Args:
        path: Path to ``.csv`` or ``.gpkg`` labeled dataset.

    Returns:
        Loaded dataframe with feature and label columns.
    """
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return pd.read_csv(source)
    if source.suffix.lower() == ".gpkg":
        return gpd.read_file(source)
    msg = f"Unsupported labeled dataset format: {source}"
    raise ValueError(msg)


def train_stand_classifier(
    labeled_data: pd.DataFrame | gpd.GeoDataFrame,
    config: TrainingConfig,
    *,
    output_dir: Path | str,
    feature_columns: list[str] | None = None,
) -> StandClassifierArtifact:
    """Train gradient boosting models and save a versioned artifact.

    Args:
        labeled_data: Labeled objects with features and stand attributes.
        config: Training hyperparameters and metadata description.
        output_dir: Directory where the versioned artifact will be written.
        feature_columns: Optional explicit feature list.

    Returns:
        Trained ``StandClassifierArtifact`` also persisted to ``output_dir``.
    """
    x_matrix, y_cover, y_canopy, feature_columns = labeled_frame_to_features(
        labeled_data,
        feature_columns=feature_columns,
        cover_type_column=config.cover_type_column,
        canopy_closure_column=config.canopy_closure_column,
    )

    x_train, x_test, y_cover_train, y_cover_test, y_canopy_train, y_canopy_test = train_test_split(
        x_matrix,
        y_cover,
        y_canopy,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y_cover,
    )

    cover_model = GradientBoostingClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        random_state=config.random_state,
        verbose=config.verbose,
    )
    canopy_model = GradientBoostingClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        random_state=config.random_state,
        verbose=config.verbose,
    )
    cover_weights = (
        compute_sample_weight(config.class_weight, y_cover_train)
        if config.class_weight
        else None
    )
    canopy_weights = (
        compute_sample_weight(config.class_weight, y_canopy_train)
        if config.class_weight
        else None
    )
    cover_model.fit(x_train, y_cover_train, sample_weight=cover_weights)
    canopy_model.fit(x_train, y_canopy_train, sample_weight=canopy_weights)

    cover_pred = cover_model.predict(x_test)
    canopy_pred = canopy_model.predict(x_test)
    metrics = compute_object_classification_metrics(
        y_cover_test,
        cover_pred,
        y_canopy_test,
        canopy_pred,
    )

    model_id = new_model_id()
    metadata = ModelMetadata(
        model_id=model_id,
        workflow="stand_delineation",
        training_date=datetime.now(tz=UTC).isoformat(),
        training_data_description=config.training_data_description,
        feature_columns=tuple(feature_columns),
        cover_type_classes=tuple(sorted(set(y_cover))),
        canopy_closure_classes=tuple(sorted(set(y_canopy))),
        validation_metrics=metrics.to_dict(),
        sklearn_version=sklearn.__version__,
    )
    artifact = StandClassifierArtifact(
        cover_type_model=cover_model,
        canopy_closure_model=canopy_model,
        metadata=metadata,
    )
    save_model_artifact(artifact, output_dir)

    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "event": "training_complete",
                "model_id": model_id,
                "overall_accuracy": metrics.overall_accuracy,
                "output_dir": str(output_dir),
            },
            sort_keys=True,
        )
    )
    return artifact


def load_trained_classifier(model_dir: Path | str) -> StandClassifierArtifact:
    """Load a trained stand classifier artifact."""
    return load_model_artifact(model_dir)
