"""Configurable classification parameters for reproducible OBIA jobs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ClassificationWorkflow(str, Enum):
    """Supported classification workflow identifiers."""

    STAND_DELINEATION = "stand_delineation"
    WETLAND = "wetland"
    LULC = "lulc"


class ClassifierBackend(str, Enum):
    """Supported classifier backend implementations."""

    GRADIENT_BOOSTING = "gradient_boosting"
    DEEP = "deep"


@dataclass(frozen=True)
class ClassificationConfig:
    """Job-level classification parameters logged with every result.

    Expected input assumptions:
        - Input objects are GeoDataFrames produced by ``terra_core.segmentation``
          with spectral mean/std and shape metric columns.
        - Feature columns must match those used during model training.

    Attributes:
        workflow: Workflow identifier (default stand delineation).
        backend: Classifier implementation to use.
        model_artifact_path: Path to a versioned model artifact directory.
        min_confidence: Objects below this confidence may be flagged for review.
    """

    workflow: ClassificationWorkflow = ClassificationWorkflow.STAND_DELINEATION
    backend: ClassifierBackend = ClassifierBackend.GRADIENT_BOOSTING
    model_artifact_path: Path | None = None
    min_confidence: float = 0.5

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable parameter record for audit trails."""
        data = asdict(self)
        data["workflow"] = self.workflow.value
        data["backend"] = self.backend.value
        data["model_artifact_path"] = (
            str(self.model_artifact_path) if self.model_artifact_path else None
        )
        return data
