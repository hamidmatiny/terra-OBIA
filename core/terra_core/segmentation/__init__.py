"""Image segmentation modules for object-based analysis."""

from terra_core.segmentation.base import SegmentationModel
from terra_core.segmentation.classical import ClassicalSegmenter
from terra_core.segmentation.config import SegmentationBackend, SegmentationConfig
from terra_core.segmentation.deep import DeepSegmenter
from terra_core.segmentation.factory import create_segmenter
from terra_core.segmentation.merge import (
    MergeContext,
    merge_tile_segmentations,
    tile_ownership_mask,
    validate_merge_coverage,
)
from terra_core.segmentation.models import (
    ObjectFeatures,
    SegmentationResult,
    TileSegmentationResult,
)

__all__ = [
    "ClassicalSegmenter",
    "DeepSegmenter",
    "MergeContext",
    "ObjectFeatures",
    "SegmentationBackend",
    "SegmentationConfig",
    "SegmentationModel",
    "SegmentationResult",
    "TileSegmentationResult",
    "create_segmenter",
    "merge_tile_segmentations",
    "tile_ownership_mask",
    "validate_merge_coverage",
]
