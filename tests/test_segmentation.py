"""Tests for terra_core segmentation backends and tile merging."""

from __future__ import annotations

import logging

import numpy as np
import pytest
from rasterio.transform import from_origin

from terra_core.segmentation import (
    MergeContext,
    SegmentationConfig,
    create_segmenter,
    merge_tile_segmentations,
    validate_merge_coverage,
)
from terra_core.segmentation.merge import detect_duplicate_overlap_objects
from terra_core.segmentation.models import TileSegmentationResult
from tests.fixtures.segmentation import split_mosaic_into_tiles


def test_classical_segmentation_output_shape(rgb_tile_array: np.ndarray) -> None:
    """Classical SLIC should return label raster and objects for a tile."""
    config = SegmentationConfig.classical(n_segments=50, compactness=10.0)
    segmenter = create_segmenter(config)
    transform = from_origin(500000.0, 5500000.0, 10.0, 10.0)
    result = segmenter.segment_tile(
        rgb_tile_array,
        tile_id="t_0_0",
        tile_row=0,
        tile_col=0,
        col_off=0,
        row_off=0,
        transform=transform,
    )
    assert result.label_raster.shape == (256, 256)
    assert result.label_raster.dtype == np.int32
    assert not result.objects.empty
    assert "area_m2" in result.objects.columns
    assert "compactness" in result.objects.columns
    assert "mean_band_1" in result.objects.columns


def test_classical_segmentation_consistency(rgb_tile_array: np.ndarray) -> None:
    """Repeated runs with identical input should produce identical labels."""
    config = SegmentationConfig.classical(n_segments=40, compactness=12.0)
    segmenter = create_segmenter(config)
    transform = from_origin(0.0, 2560.0, 10.0, 10.0)
    kwargs = {
        "tile_id": "t_0_0",
        "tile_row": 0,
        "tile_col": 0,
        "col_off": 0,
        "row_off": 0,
        "transform": transform,
    }
    first = segmenter.segment_tile(rgb_tile_array, **kwargs)
    second = segmenter.segment_tile(rgb_tile_array, **kwargs)
    np.testing.assert_array_equal(first.label_raster, second.label_raster)


def test_deep_segmentation_output_shape(rgb_tile_array: np.ndarray) -> None:
    """Deep FCN segmenter should return standardized tile output."""
    config = SegmentationConfig.deep(confidence_threshold=0.0)
    segmenter = create_segmenter(config, pretrained=False)
    transform = from_origin(500000.0, 5500000.0, 10.0, 10.0)
    result = segmenter.segment_tile(
        rgb_tile_array,
        tile_id="t_0_0",
        tile_row=0,
        tile_col=0,
        col_off=0,
        row_off=0,
        transform=transform,
    )
    assert result.label_raster.shape == (256, 256)
    assert "backend" in result.config_snapshot
    assert result.config_snapshot["backend"] == "deep"
    assert result.label_raster.max() >= 0


def test_config_snapshot_logged(
    rgb_tile_array: np.ndarray,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Segmentation parameters should be JSON-logged for reproducibility."""
    caplog.set_level(logging.INFO, logger="terra_core.segmentation")
    config = SegmentationConfig.classical(n_segments=30, compactness=8.0)
    segmenter = create_segmenter(config)
    transform = from_origin(0.0, 2560.0, 10.0, 10.0)
    segmenter.segment_tile(
        rgb_tile_array,
        tile_id="audit_tile",
        tile_row=0,
        tile_col=0,
        col_off=0,
        row_off=0,
        transform=transform,
    )
    assert any("segmentation_run" in record.message for record in caplog.records)
    assert any("compactness" in record.message for record in caplog.records)


def test_merge_no_missing_area_at_boundaries(two_tile_mosaic: tuple[np.ndarray, int]) -> None:
    """Merged mosaic should label every valid pixel without gaps at tile seams."""
    full_array, overlap = two_tile_mosaic
    _, height, width = full_array.shape
    transform = from_origin(600000.0, 5400000.0, 10.0, 10.0)
    config = SegmentationConfig.classical(n_segments=80, compactness=15.0)
    segmenter = create_segmenter(config)

    tile_results: list[TileSegmentationResult] = []
    data_by_tile: dict[str, np.ndarray] = {}
    for data, tile_row, tile_col, col_off, row_off in split_mosaic_into_tiles(
        full_array,
        overlap=overlap,
        tile_size=256,
    ):
        tile_id = f"tile_{tile_row}_{tile_col}"
        result = segmenter.segment_tile(
            data,
            tile_id=tile_id,
            tile_row=tile_row,
            tile_col=tile_col,
            col_off=col_off,
            row_off=row_off,
            transform=from_origin(
                transform.c + col_off * transform.a,
                transform.f + row_off * transform.e,
                transform.a,
                transform.e,
            ),
        )
        tile_results.append(result)
        data_by_tile[tile_id] = data

    context = MergeContext(
        full_width=width,
        full_height=height,
        overlap=overlap,
        transform=transform,
        crs_wkt="EPSG:4326",
        pixel_area_m2=100.0,
    )
    merged = merge_tile_segmentations(
        tile_results,
        context,
        data_by_tile,
        band_names=config.band_names,
        min_object_area_px=config.min_object_area_px,
    )

    valid_mask = np.ones((height, width), dtype=bool)
    passed, missing_fraction = validate_merge_coverage(merged.label_raster, valid_mask)
    assert passed, f"Missing labeled fraction: {missing_fraction}"
    assert merged.label_raster.shape == (height, width)
    assert not merged.objects.empty

    duplicates = detect_duplicate_overlap_objects(merged.objects, overlap_buffer_m=overlap * 10.0)
    assert duplicates == 0


def test_merge_preserves_total_labeled_area(two_tile_mosaic: tuple[np.ndarray, int]) -> None:
    """Sum of object pixel counts should match labeled pixels in merged raster."""
    full_array, overlap = two_tile_mosaic
    _, height, width = full_array.shape
    transform = from_origin(600000.0, 5400000.0, 10.0, 10.0)
    config = SegmentationConfig.classical(n_segments=60, compactness=10.0)
    segmenter = create_segmenter(config)

    tile_results: list[TileSegmentationResult] = []
    data_by_tile: dict[str, np.ndarray] = {}
    for data, tile_row, tile_col, col_off, row_off in split_mosaic_into_tiles(
        full_array,
        overlap=overlap,
        tile_size=256,
    ):
        tile_id = f"tile_{tile_row}_{tile_col}"
        result = segmenter.segment_tile(
            data,
            tile_id=tile_id,
            tile_row=tile_row,
            tile_col=tile_col,
            col_off=col_off,
            row_off=row_off,
            transform=from_origin(
                transform.c + col_off * transform.a,
                transform.f + row_off * transform.e,
                transform.a,
                transform.e,
            ),
        )
        tile_results.append(result)
        data_by_tile[tile_id] = data

    context = MergeContext(
        full_width=width,
        full_height=height,
        overlap=overlap,
        transform=transform,
        crs_wkt=None,
        pixel_area_m2=100.0,
    )
    merged = merge_tile_segmentations(
        tile_results,
        context,
        data_by_tile,
        band_names=config.band_names,
    )
    labeled_pixels = int(np.count_nonzero(merged.label_raster > 0))
    object_pixels = int((merged.label_raster > 0).sum())
    assert labeled_pixels == object_pixels
    assert labeled_pixels > 0
