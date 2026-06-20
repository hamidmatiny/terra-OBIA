"""Versioned model artifact persistence and loading."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib

from terra_core.classification.models import ModelMetadata

logger = logging.getLogger("terra_core.classification")


@dataclass
class StandClassifierArtifact:
    """On-disk bundle for a trained stand delineation classifier."""

    cover_type_model: Any
    canopy_closure_model: Any
    metadata: ModelMetadata

    def predict_proba_cover(self, features: Any) -> Any:
        """Predict cover-type probabilities."""
        return self.cover_type_model.predict_proba(features)

    def predict_proba_canopy(self, features: Any) -> Any:
        """Predict canopy-closure probabilities."""
        return self.canopy_closure_model.predict_proba(features)


def save_model_artifact(
    artifact: StandClassifierArtifact,
    output_dir: Path | str,
) -> Path:
    """Save a versioned model artifact directory for audit trails.

    Layout::

        {output_dir}/
            metadata.json
            cover_type_model.joblib
            canopy_closure_model.joblib

    Args:
        artifact: Trained models and metadata.
        output_dir: Destination directory (created if missing).

    Returns:
        Path to the saved artifact directory.
    """
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    joblib.dump(artifact.cover_type_model, directory / "cover_type_model.joblib")
    joblib.dump(artifact.canopy_closure_model, directory / "canopy_closure_model.joblib")
    metadata_path = directory / "metadata.json"
    metadata_path.write_text(json.dumps(artifact.metadata.to_dict(), indent=2), encoding="utf-8")

    log_payload = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "event": "model_saved",
        "model_id": artifact.metadata.model_id,
        "workflow": artifact.metadata.workflow,
        "training_date": artifact.metadata.training_date,
        "validation_metrics": artifact.metadata.validation_metrics,
        "path": str(directory),
    }
    logger.info(json.dumps(log_payload, sort_keys=True))
    return directory


def load_model_artifact(model_dir: Path | str) -> StandClassifierArtifact:
    """Load a versioned stand classifier artifact from disk.

    Args:
        model_dir: Directory previously written by ``save_model_artifact``.

    Returns:
        Loaded ``StandClassifierArtifact``.
    """
    directory = Path(model_dir)
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    model_metadata = ModelMetadata(
        model_id=metadata["model_id"],
        workflow=metadata["workflow"],
        training_date=metadata["training_date"],
        training_data_description=metadata["training_data_description"],
        feature_columns=tuple(metadata["feature_columns"]),
        cover_type_classes=tuple(metadata["cover_type_classes"]),
        canopy_closure_classes=tuple(metadata["canopy_closure_classes"]),
        validation_metrics=metadata["validation_metrics"],
        sklearn_version=metadata["sklearn_version"],
        notes=metadata.get("notes", ""),
    )
    artifact = StandClassifierArtifact(
        cover_type_model=joblib.load(directory / "cover_type_model.joblib"),
        canopy_closure_model=joblib.load(directory / "canopy_closure_model.joblib"),
        metadata=model_metadata,
    )
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "event": "model_loaded",
                "model_id": model_metadata.model_id,
                "path": str(directory),
            },
            sort_keys=True,
        )
    )
    return artifact


def new_model_id(prefix: str = "stand") -> str:
    """Generate a unique model identifier."""
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{timestamp}_{uuid4().hex[:8]}"
