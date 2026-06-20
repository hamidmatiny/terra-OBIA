"""Base interfaces for learned segmentation models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SegmentationModel(ABC):
    """Abstract segmentation model for tile-based inference.

    Implementations consume numpy arrays produced by ``CogReader.read_window``
    and return per-pixel or instance labels aligned to the input tile. Models
    assume input arrays match the source raster's native resolution; resampling
    is the caller's responsibility.
    """

    @abstractmethod
    def predict(self, tile: Any) -> Any:
        """Run segmentation on a single image tile.

        Args:
            tile: Array with shape ``(bands, height, width)`` at native GSD.

        Returns:
            Segmentation output aligned to the input tile dimensions.
        """
        ...
