"""Classical SLIC superpixel segmentation baseline."""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray
from rasterio.transform import Affine
from skimage.segmentation import slic

from terra_core.segmentation.base import SegmentationModel
from terra_core.segmentation.models import TileSegmentationResult
from terra_core.segmentation.reproducibility import log_segmentation_run
from terra_core.segmentation.vectorize import vectorize_labels

logger = logging.getLogger("terra_core.segmentation")


def _to_rgb(data: NDArray[np.floating]) -> NDArray[np.floating]:
    """Map input bands to 3-channel RGB-like array for SLIC.

    Expected CRS/resolution assumptions:
        - Uses first band repeated when fewer than 3 bands are available.
    """
    bands, _, _ = data.shape
    if bands >= 3:
        rgb = data[:3]
    elif bands == 2:
        rgb = np.stack([data[0], data[1], data[1]], axis=0)
    else:
        rgb = np.repeat(data[:1], 3, axis=0)
    rgb = np.moveaxis(rgb, 0, -1)
    lower = float(np.nanmin(rgb))
    upper = float(np.nanmax(rgb))
    if upper > lower:
        rgb = (rgb - lower) / (upper - lower)
    return rgb.astype(np.float64)


class ClassicalSegmenter(SegmentationModel):
    """SLIC superpixel segmenter for baseline and comparison workflows.

    Expected CRS/resolution assumptions:
        - Input tiles are multispectral or RGB at native GSD (typically 0.5–10 m
          for forestry/aerial products).
        - ``n_segments`` and ``compactness`` mirror eCognition scale/compactness
          tuning knobs for reproducible classical runs.
    """

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
        """Run SLIC on one tile and vectorize objects."""
        masked = np.ma.masked_invalid(data)
        if nodata is not None:
            masked = np.ma.masked_where(data == nodata, masked)

        rgb = _to_rgb(np.asarray(masked.filled(np.nan)))
        labels = slic(
            rgb,
            n_segments=self.config.n_segments,
            compactness=self.config.compactness,
            sigma=self.config.sigma,
            start_label=1,
            channel_axis=-1,
        ).astype(np.int32)

        if nodata is not None:
            nodata_mask = np.any(data == nodata, axis=0)
            labels[nodata_mask] = 0

        objects = vectorize_labels(
            labels,
            np.asarray(data, dtype=np.float64),
            transform,
            crs_wkt=None,
            band_names=self.config.band_names,
            min_object_area_px=self.config.min_object_area_px,
        )
        snapshot = self.config_snapshot
        log_segmentation_run(logger, tile_id=tile_id, config=snapshot, backend="classical")
        return TileSegmentationResult(
            tile_id=tile_id,
            tile_row=tile_row,
            tile_col=tile_col,
            col_off=col_off,
            row_off=row_off,
            label_raster=labels,
            objects=objects,
            transform=transform,
            config_snapshot=snapshot,
        )
