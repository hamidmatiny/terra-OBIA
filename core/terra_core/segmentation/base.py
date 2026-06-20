"""Base interfaces for tile-based segmentation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray
from rasterio.transform import Affine

from terra_core.segmentation.config import SegmentationConfig
from terra_core.segmentation.models import TileSegmentationResult


class SegmentationModel(ABC):
    """Abstract segmentation backend for OBIA tile inference.

    Implementations consume numpy arrays produced by pipeline tile readers and
    return a standardized label raster plus vector objects with spectral/shape
    statistics. All backends must log their configuration snapshot for
    reproducibility.

    Expected CRS/resolution assumptions:
        - Input ``data`` has shape ``(bands, height, width)`` at native GSD.
        - ``transform`` georeferences the tile origin in the source CRS.
        - No reprojection or resampling is performed inside ``segment_tile``.
    """

    def __init__(self, config: SegmentationConfig) -> None:
        """Store job configuration used for inference and audit logging."""
        self.config = config

    @abstractmethod
    def segment_tile(
        self,
        data: NDArray[np.floating],
        *,
        tile_id: str,
        tile_row: int,
        tile_col: int,
        col_off: int,
        row_off: int,
        transform: Affine,
        nodata: float | None = None,
    ) -> TileSegmentationResult:
        """Segment one tile and return the internal OBIA representation.

        Args:
            data: Pixel array ``(bands, height, width)`` at native resolution.
            tile_id: Catalog tile identifier.
            tile_row: Tile row index in the processing grid.
            tile_col: Tile column index in the processing grid.
            col_off: Column offset in the parent raster (pixels).
            row_off: Row offset in the parent raster (pixels).
            transform: Affine transform of this tile window.
            nodata: Optional nodata value to mask before segmentation.

        Returns:
            ``TileSegmentationResult`` with label raster and object features.
        """

    @property
    def config_snapshot(self) -> dict[str, object]:
        """Return serializable parameters for reproducibility logging."""
        return self.config.snapshot()
