"""Segmentation result and object feature data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import numpy as np
from numpy.typing import NDArray
from rasterio.transform import Affine


@dataclass(frozen=True)
class ObjectFeatures:
    """Object-level features analogous to eCognition export attributes.

    Expected CRS/resolution assumptions:
        - ``area_m2`` and ``perimeter_m`` are computed in the source CRS using
          the pixel geotransform (typically metres for UTM forestry products).
        - Spectral statistics are computed from input bands at native GSD.
    """

    object_id: int
    area_m2: float
    perimeter_m: float
    compactness: float
    band_means: dict[str, float]
    band_stds: dict[str, float]


@dataclass
class TileSegmentationResult:
    """Per-tile segmentation output before mosaic merge."""

    tile_id: str
    tile_row: int
    tile_col: int
    col_off: int
    row_off: int
    label_raster: NDArray[np.int32]
    objects: gpd.GeoDataFrame
    transform: Affine
    config_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class SegmentationResult:
    """Merged segmentation output for a full raster extent."""

    label_raster: NDArray[np.int32]
    objects: gpd.GeoDataFrame
    config_snapshot: dict[str, Any]
    merge_metadata: dict[str, Any]
    transform: Affine
    crs_wkt: str | None
