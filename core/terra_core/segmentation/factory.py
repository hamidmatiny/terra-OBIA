"""Segmentation backend factory."""

from __future__ import annotations

from terra_core.segmentation.base import SegmentationModel
from terra_core.segmentation.classical import ClassicalSegmenter
from terra_core.segmentation.config import SegmentationBackend, SegmentationConfig
from terra_core.segmentation.deep import DeepSegmenter


def create_segmenter(
    config: SegmentationConfig,
    *,
    pretrained: bool = True,
    device: str | None = None,
) -> SegmentationModel:
    """Instantiate a segmentation backend from job configuration.

    Args:
        config: Job-level segmentation parameters.
        pretrained: When True, load pretrained FCN weights for the deep backend.
        device: Optional torch device string (``cpu`` or ``cuda``).

    Returns:
        Configured ``SegmentationModel`` implementation.
    """
    if config.backend == SegmentationBackend.CLASSICAL:
        return ClassicalSegmenter(config)
    if config.backend == SegmentationBackend.DEEP:
        return DeepSegmenter(config, pretrained=pretrained, device=device)
    msg = f"Unsupported segmentation backend: {config.backend}"
    raise ValueError(msg)
