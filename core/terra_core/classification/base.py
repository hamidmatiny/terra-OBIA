"""Base interfaces for segment classification models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ClassificationModel(ABC):
    """Abstract classifier for segment-level thematic labeling.

    Classifiers operate on feature vectors derived from segmented objects.
    Geographic context (CRS, area units) must be encoded in features upstream;
    this interface does not perform coordinate transforms.
    """

    @abstractmethod
    def predict(self, features: Any) -> Any:
        """Assign thematic class labels to segment feature vectors.

        Args:
            features: Tabular or structured features per segment/object.

        Returns:
            Predicted class label(s) for each input segment.
        """
        ...
