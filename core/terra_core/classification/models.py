"""Classification result and stand attribute data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd


@dataclass(frozen=True)
class StandAttributes:
    """Stand-level thematic attributes assigned to one segmented object.

    Expected CRS/resolution assumptions:
        - Attributes describe the object polygon in the source CRS at native
          GSD; no reprojection is performed during classification.
    """

    object_id: int
    cover_type: str
    canopy_closure_class: str
    confidence: float


@dataclass
class ClassificationResult:
    """Output of a classification workflow applied to segmented objects."""

    objects: gpd.GeoDataFrame
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    model_version: str = "untrained"
    workflow: str = "stand_delineation"


@dataclass(frozen=True)
class ModelMetadata:
    """Audit metadata stored with every versioned model artifact."""

    model_id: str
    workflow: str
    training_date: str
    training_data_description: str
    feature_columns: tuple[str, ...]
    cover_type_classes: tuple[str, ...]
    canopy_closure_classes: tuple[str, ...]
    validation_metrics: dict[str, Any]
    sklearn_version: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata for JSON storage."""
        return {
            "model_id": self.model_id,
            "workflow": self.workflow,
            "training_date": self.training_date,
            "training_data_description": self.training_data_description,
            "feature_columns": list(self.feature_columns),
            "cover_type_classes": list(self.cover_type_classes),
            "canopy_closure_classes": list(self.canopy_closure_classes),
            "validation_metrics": self.validation_metrics,
            "sklearn_version": self.sklearn_version,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AccuracyReport:
    """Accuracy metrics computed against held-out labeled data."""

    overall_accuracy: float
    cover_type_metrics: dict[str, dict[str, float]]
    canopy_closure_metrics: dict[str, dict[str, float]]
    mean_iou: float
    per_class_iou: dict[str, float]
    support: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics for Markdown/JSON reports."""
        return {
            "overall_accuracy": self.overall_accuracy,
            "cover_type_metrics": self.cover_type_metrics,
            "canopy_closure_metrics": self.canopy_closure_metrics,
            "mean_iou": self.mean_iou,
            "per_class_iou": self.per_class_iou,
            "support": self.support,
        }
