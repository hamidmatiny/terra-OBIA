"""Forest stand delineation classifier for segmented OBIA objects."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import geopandas as gpd
import numpy as np

from terra_core.classification.base import ClassificationModel
from terra_core.classification.config import ClassificationConfig
from terra_core.classification.features import objects_to_feature_matrix
from terra_core.classification.models import ClassificationResult
from terra_core.classification.registry import StandClassifierArtifact, load_model_artifact

logger = logging.getLogger("terra_core.classification")


class StandDelineationClassifier(ClassificationModel):
    """Assign stand attributes to segmented objects using a trained model.

    Expected CRS/resolution assumptions:
        - Input objects originate from ``terra_core.segmentation`` at native GSD.
        - Feature columns must match the saved model artifact metadata.

    Outputs per object:
        - ``cover_type`` — dominant cover class (e.g. conifer, deciduous, mixed)
        - ``canopy_closure_class`` — approximate closure bin (open/sparse/moderate/dense)
        - ``confidence`` — minimum predicted class probability across both heads
    """

    def __init__(
        self,
        config: ClassificationConfig,
        artifact: StandClassifierArtifact | None = None,
    ) -> None:
        """Configure classifier and optionally load a trained artifact."""
        super().__init__(config)
        if artifact is not None:
            self._artifact = artifact
        elif config.model_artifact_path is not None:
            self._artifact = load_model_artifact(config.model_artifact_path)
        else:
            msg = "StandDelineationClassifier requires a trained model artifact."
            raise ValueError(msg)

    @property
    def model_version(self) -> str:
        """Return the loaded model identifier."""
        return self._artifact.metadata.model_id

    def classify_objects(self, objects: gpd.GeoDataFrame) -> ClassificationResult:
        """Predict stand attributes for segmented objects."""
        if objects.empty:
            return ClassificationResult(
                objects=objects.copy(),
                config_snapshot=self.config_snapshot,
                model_version=self.model_version,
                workflow="stand_delineation",
            )

        feature_columns = list(self._artifact.metadata.feature_columns)
        features = objects_to_feature_matrix(objects, feature_columns)

        cover_pred = self._artifact.cover_type_model.predict(features)
        canopy_pred = self._artifact.canopy_closure_model.predict(features)
        cover_proba = self._artifact.predict_proba_cover(features)
        canopy_proba = self._artifact.predict_proba_canopy(features)

        cover_conf = _max_predicted_proba(cover_proba)
        canopy_conf = _max_predicted_proba(canopy_proba)
        confidence = np.minimum(cover_conf, canopy_conf)

        enriched = objects.copy()
        enriched["cover_type"] = cover_pred
        enriched["canopy_closure_class"] = canopy_pred
        enriched["confidence"] = confidence
        enriched["needs_review"] = confidence < self.config.min_confidence

        snapshot = self.config_snapshot
        snapshot["model_id"] = self.model_version
        snapshot["model_training_date"] = self._artifact.metadata.training_date

        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "event": "classification_run",
                    "workflow": "stand_delineation",
                    "model_id": self.model_version,
                    "object_count": len(enriched),
                    "parameters": snapshot,
                },
                sort_keys=True,
            )
        )
        return ClassificationResult(
            objects=enriched,
            config_snapshot=snapshot,
            model_version=self.model_version,
            workflow="stand_delineation",
        )


def _max_predicted_proba(proba: np.ndarray) -> np.ndarray:
    """Return the maximum class probability for each row."""
    return np.max(proba, axis=1)  # type: ignore[no-any-return]
