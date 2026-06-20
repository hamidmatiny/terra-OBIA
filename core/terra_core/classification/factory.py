"""Classifier backend factory."""

from __future__ import annotations

from terra_core.classification.base import ClassificationModel
from terra_core.classification.config import ClassificationConfig, ClassificationWorkflow
from terra_core.classification.registry import StandClassifierArtifact
from terra_core.classification.stand_delineation import StandDelineationClassifier


def create_classifier(
    config: ClassificationConfig,
    *,
    artifact: StandClassifierArtifact | None = None,
) -> ClassificationModel:
    """Instantiate a classification backend from job configuration.

    Args:
        config: Job-level classification parameters.
        artifact: Optional pre-loaded model artifact.

    Returns:
        Configured ``ClassificationModel`` implementation.
    """
    if config.workflow == ClassificationWorkflow.STAND_DELINEATION:
        return StandDelineationClassifier(config, artifact=artifact)
    msg = f"Unsupported classification workflow: {config.workflow}"
    raise ValueError(msg)
