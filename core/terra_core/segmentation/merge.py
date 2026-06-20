"""Merge per-tile label rasters across overlap regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import geopandas as gpd
import numpy as np
from numpy.typing import NDArray
from rasterio.transform import Affine

from terra_core.segmentation.models import SegmentationResult, TileSegmentationResult
from terra_core.segmentation.vectorize import vectorize_labels


@dataclass(frozen=True)
class MergeContext:
    """Mosaic context required for overlap-aware tile merging.

    Expected CRS/resolution assumptions:
        - All tiles share the parent raster CRS and GSD.
        - ``full_width``/``full_height`` match the source raster dimensions.
    """

    full_width: int
    full_height: int
    overlap: int
    transform: Affine
    crs_wkt: str | None
    pixel_area_m2: float


def tile_ownership_mask(
    height: int,
    width: int,
    overlap: int,
    *,
    is_left_edge: bool,
    is_right_edge: bool,
    is_top_edge: bool,
    is_bottom_edge: bool,
) -> NDArray[np.float32]:
    """Compute per-pixel ownership weight for overlap reconciliation.

    Pixels closer to the tile interior receive higher weight. Mosaic edges are
    treated as infinite distance so border tiles are not penalized.

    Args:
        height: Tile height in pixels.
        width: Tile width in pixels.
        overlap: Overlap width in pixels from the tiling grid.
        is_left_edge: True when this tile touches the mosaic left border.
        is_right_edge: True when this tile touches the mosaic right border.
        is_top_edge: True when this tile touches the mosaic top border.
        is_bottom_edge: True when this tile touches the mosaic bottom border.

    Returns:
        Ownership weights ``(height, width)``; higher values win in overlaps.
    """
    yy, xx = np.ogrid[:height, :width]
    dist_top = yy.astype(np.float32)
    dist_bottom = (height - 1 - yy).astype(np.float32)
    dist_left = xx.astype(np.float32)
    dist_right = (width - 1 - xx).astype(np.float32)

    if is_top_edge:
        dist_top += overlap
    if is_bottom_edge:
        dist_bottom += overlap
    if is_left_edge:
        dist_left += overlap
    if is_right_edge:
        dist_right += overlap

    vertical = np.minimum(dist_top, dist_bottom)
    horizontal = np.minimum(dist_left, dist_right)
    return cast(
        NDArray[np.float32],
        np.minimum(vertical, horizontal).astype(np.float32),
    )


def merge_tile_segmentations(
    tile_results: list[TileSegmentationResult],
    context: MergeContext,
    data_by_tile: dict[str, NDArray[np.floating]],
    *,
    band_names: tuple[str, ...],
    min_object_area_px: int = 16,
) -> SegmentationResult:
    """Merge tile label rasters into a seamless mosaic using overlap ownership.

    Expected CRS/resolution assumptions:
        - Each tile result aligns with its ``col_off``/``row_off`` placement.
        - ``data_by_tile`` provides spectral arrays keyed by ``tile_id`` for
          final object statistics at native GSD.

    Merge strategy:
        1. For each pixel, select the label from the tile with highest ownership
           weight in the overlap zone (interior pixels beat edge pixels).
        2. Break ties by preferring the numerically smaller label value.
        3. Re-vectorize the merged label raster into global object polygons.

    Args:
        tile_results: Per-tile segmentation outputs.
        context: Mosaic dimensions and georeferencing.
        data_by_tile: Spectral arrays for zonal statistics after merge.
        band_names: Band names for object feature columns.
        min_object_area_px: Minimum object size after merge.

    Returns:
        ``SegmentationResult`` covering the full mosaic extent.
    """
    global_labels = np.zeros((context.full_height, context.full_width), dtype=np.int32)
    ownership = np.full((context.full_height, context.full_width), -1.0, dtype=np.float32)

    for result in tile_results:
        height, width = result.label_raster.shape
        is_left = result.col_off == 0
        is_top = result.row_off == 0
        is_right = result.col_off + width >= context.full_width
        is_bottom = result.row_off + height >= context.full_height

        local_owner = tile_ownership_mask(
            height,
            width,
            context.overlap,
            is_left_edge=is_left,
            is_right_edge=is_right,
            is_top_edge=is_top,
            is_bottom_edge=is_bottom,
        )

        row_slice = slice(result.row_off, result.row_off + height)
        col_slice = slice(result.col_off, result.col_off + width)
        owner_view = ownership[row_slice, col_slice]
        label_view = global_labels[row_slice, col_slice]
        local_labels = result.label_raster

        wins = local_owner > owner_view
        ties = (local_owner == owner_view) & (owner_view >= 0)
        tie_break = ties & (local_labels < label_view)
        update_mask = wins | tie_break | (owner_view < 0)

        label_view[update_mask] = local_labels[update_mask]
        owner_view[update_mask] = local_owner[update_mask]

    # Build a synthetic full-band array for zonal stats by stitching tile data.
    band_count = next(iter(data_by_tile.values())).shape[0]
    full_data = np.zeros((band_count, context.full_height, context.full_width), dtype=np.float64)
    full_owner = np.full((context.full_height, context.full_width), -1.0, dtype=np.float32)
    for result in tile_results:
        data = data_by_tile[result.tile_id]
        height, width = data.shape[1], data.shape[2]
        local_owner = tile_ownership_mask(
            height,
            width,
            context.overlap,
            is_left_edge=result.col_off == 0,
            is_right_edge=result.col_off + width >= context.full_width,
            is_top_edge=result.row_off == 0,
            is_bottom_edge=result.row_off + height >= context.full_height,
        )
        row_slice = slice(result.row_off, result.row_off + height)
        col_slice = slice(result.col_off, result.col_off + width)
        owner_view = full_owner[row_slice, col_slice]
        update = local_owner >= owner_view
        for band_idx in range(band_count):
            band_view = full_data[band_idx, row_slice, col_slice]
            band_view[update] = data[band_idx][update]
        owner_view[update] = local_owner[update]

    objects = vectorize_labels(
        global_labels,
        full_data,
        context.transform,
        crs_wkt=context.crs_wkt,
        band_names=band_names,
        min_object_area_px=min_object_area_px,
        pixel_area_m2=context.pixel_area_m2,
    )

    config_snapshot = tile_results[0].config_snapshot if tile_results else {}
    merge_metadata = {
        "tile_count": len(tile_results),
        "overlap_px": context.overlap,
        "strategy": "ownership_weighted",
        "full_width": context.full_width,
        "full_height": context.full_height,
    }
    return SegmentationResult(
        label_raster=global_labels,
        objects=objects,
        config_snapshot=config_snapshot,
        merge_metadata=merge_metadata,
        transform=context.transform,
        crs_wkt=context.crs_wkt,
    )


def coverage_mask(label_raster: NDArray[np.int32]) -> NDArray[np.bool_]:
    """Return True for pixels assigned to any object (label > 0)."""
    return label_raster > 0


def validate_merge_coverage(
    label_raster: NDArray[np.int32],
    valid_mask: NDArray[np.bool_],
) -> tuple[bool, float]:
    """Check that all valid pixels are labeled exactly once.

    Args:
        label_raster: Merged label raster.
        valid_mask: True where pixels should carry a label (non-nodata extent).

    Returns:
        Tuple of ``(passed, missing_fraction)`` where missing_fraction is the
        proportion of valid pixels with label 0 after merge.
    """
    required = valid_mask
    labeled = coverage_mask(label_raster)
    missing = required & ~labeled
    if not np.any(required):
        return True, 0.0
    missing_fraction = float(np.count_nonzero(missing) / np.count_nonzero(required))
    return missing_fraction == 0.0, missing_fraction


def detect_duplicate_overlap_objects(objects: gpd.GeoDataFrame, overlap_buffer_m: float) -> int:
    """Count likely duplicate polygons near tile seams.

    Args:
        objects: Merged object GeoDataFrame in source CRS.
        overlap_buffer_m: Buffer distance around suspected seams (metres).

    Returns:
        Count of overlapping polygon pairs with IoU > 0.5 near tile boundaries.
    """
    if objects.empty:
        return 0
    duplicates = 0
    sindex = objects.sindex
    geoms = objects.geometry
    for i in range(len(objects)):
        geom = geoms.iloc[i]
        if geom is None or geom.is_empty:
            continue
        bounds = geom.buffer(overlap_buffer_m).bounds
        candidates = list(sindex.intersection(bounds))
        for j in candidates:
            if j <= i:
                continue
            other = geoms.iloc[j]
            if not geom.intersects(other):
                continue
            inter = geom.intersection(other)
            if inter.is_empty:
                continue
            union = geom.union(other)
            iou = inter.area / union.area if union.area > 0 else 0.0
            if iou > 0.5:
                duplicates += 1
    return duplicates
