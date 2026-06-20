"""Object classification modules for assigning thematic labels to segments."""

from terra_core.classification.base import ClassificationModel
from terra_core.classification.config import (
    ClassificationConfig,
    ClassificationWorkflow,
    ClassifierBackend,
)
from terra_core.classification.evaluation import (
    compute_object_classification_metrics,
    compute_polygon_iou,
    enrich_accuracy_report_with_iou,
    write_accuracy_report_markdown,
)
from terra_core.classification.factory import create_classifier
from terra_core.classification.models import AccuracyReport, ClassificationResult, ModelMetadata
from terra_core.classification.registry import (
    StandClassifierArtifact,
    load_model_artifact,
    save_model_artifact,
)
from terra_core.classification.stand_delineation import StandDelineationClassifier
from terra_core.classification.training import (
    TrainingConfig,
    load_labeled_dataset,
    train_stand_classifier,
)

__all__ = [
    "AccuracyReport",
    "ClassificationConfig",
    "ClassificationModel",
    "ClassificationResult",
    "ClassificationWorkflow",
    "ClassifierBackend",
    "ModelMetadata",
    "StandClassifierArtifact",
    "StandDelineationClassifier",
    "TrainingConfig",
    "compute_object_classification_metrics",
    "compute_polygon_iou",
    "create_classifier",
    "enrich_accuracy_report_with_iou",
    "load_labeled_dataset",
    "load_model_artifact",
    "save_model_artifact",
    "train_stand_classifier",
    "write_accuracy_report_markdown",
]
