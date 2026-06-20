"""Base interfaces for segment-level classification workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod

import geopandas as gpd

from terra_core.classification.config import ClassificationConfig
from terra_core.classification.models import ClassificationResult
from terra_core.segmentation.models import TileSegmentationResult


class ClassificationModel(ABC):
    """Abstract classifier for OBIA object-level thematic labeling.

    Implementations consume segmented objects with spectral and shape features
    and return stand-level or thematic attributes. The interface mirrors
    ``SegmentationModel`` so future workflows (wetland, LULC, species) can
    reuse the same pattern.

    Expected CRS/resolution assumptions:
        - Input ``objects`` GeoDataFrames are in the source CRS at native GSD.
        - Classifiers do not reproject geometries or resample rasters.
    """

    def __init__(self, config: ClassificationConfig) -> None:
        """Store job configuration used for inference and audit logging."""
        self.config = config

    @abstractmethod
    def classify_objects(self, objects: gpd.GeoDataFrame) -> ClassificationResult:
        """Assign thematic attributes to segmented objects.

        Args:
            objects: GeoDataFrame with geometry and feature columns from
                segmentation (``area_m2``, ``mean_band_*``, etc.).

        Returns:
            ``ClassificationResult`` with enriched object attributes.
        """

    def classify_tile(self, tile_result: TileSegmentationResult) -> ClassificationResult:
        """Classify objects from a single tile segmentation result.

        Args:
            tile_result: Output of ``SegmentationModel.segment_tile``.

        Returns:
            Classification result for the tile's objects.
        """
        return self.classify_objects(tile_result.objects)

    @property
    def config_snapshot(self) -> dict[str, object]:
        """Return serializable parameters for reproducibility logging."""
        return self.config.snapshot()
