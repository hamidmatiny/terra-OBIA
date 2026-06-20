"""Trained model discovery for the REST API."""

from __future__ import annotations

import json
from pathlib import Path

from terra_api.config import settings
from terra_api.schemas import ModelListResponse, ModelSummary


def list_available_models(models_dir: Path | None = None) -> ModelListResponse:
    """Scan the models directory for versioned classification artifacts.

    Args:
        models_dir: Override models root (defaults to ``TERRA_MODELS_DIR``).

    Returns:
        ``ModelListResponse`` with metadata and accuracy summaries.
    """
    root = models_dir or settings.models_dir
    summaries: list[ModelSummary] = []
    if not root.exists():
        return ModelListResponse(models=[])

    for metadata_path in root.rglob("metadata.json"):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        artifact_dir = metadata_path.parent
        validation = metadata.get("validation_metrics", {})
        report_path = artifact_dir / "accuracy_report.md"
        summaries.append(
            ModelSummary(
                model_id=metadata["model_id"],
                workflow=metadata.get("workflow", "stand_delineation"),
                training_date=metadata.get("training_date", ""),
                training_data_description=metadata.get("training_data_description", ""),
                overall_accuracy=validation.get("overall_accuracy"),
                mean_iou=validation.get("mean_iou"),
                artifact_path=str(artifact_dir.resolve()),
                accuracy_report_path=str(report_path.resolve()) if report_path.exists() else None,
            )
        )
    summaries.sort(key=lambda item: item.training_date, reverse=True)
    return ModelListResponse(models=summaries)


def resolve_model_path(model_id: str, models_dir: Path | None = None) -> Path:
    """Find the artifact directory for a model identifier.

    Args:
        model_id: Model ID from ``metadata.json``.
        models_dir: Override models root.

    Returns:
        Path to the model artifact directory.

    Raises:
        FileNotFoundError: When no matching model is registered.
    """
    models = list_available_models(models_dir)
    for model in models.models:
        if model.model_id == model_id:
            return Path(model.artifact_path)
    msg = f"Model not found: {model_id}"
    raise FileNotFoundError(msg)
