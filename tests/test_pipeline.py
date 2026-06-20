"""Integration tests for the Terra OBIA pipeline module."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from terra_pipeline.ingest import TileIngestionPipeline
from terra_pipeline.ingestion.reader import open_raster_profile
from terra_pipeline.processing import process_tile
from terra_pipeline.tiling.catalog import TileCatalog
from terra_pipeline.tiling.grid import TileGrid
from terra_pipeline.tiling.streaming import StreamingTileReader
from terra_pipeline.validation.raster import validate_raster_profile, validate_tile_record


def test_open_geotiff_profile(synthetic_geotiff_2500: Path) -> None:
    """GeoTIFF ingestion should expose CRS, resolution, and dimensions."""
    profile = open_raster_profile(synthetic_geotiff_2500)
    assert profile.crs_epsg == 32619
    assert profile.resolution_x == pytest.approx(10.0)
    assert profile.width == 2500
    assert profile.height == 2100


def test_crs_validation_failure(synthetic_geotiff_no_crs: Path) -> None:
    """Missing CRS should produce an error-severity validation issue."""
    profile = open_raster_profile(synthetic_geotiff_no_crs)
    report = validate_raster_profile(profile)
    assert not report.passed
    assert any(issue.code == "CRS_MISSING" for issue in report.issues)


def test_ingestion_pipeline_rejects_invalid_crs(synthetic_geotiff_no_crs: Path) -> None:
    """Pipeline should abort when source validation fails."""
    pipeline = TileIngestionPipeline(catalog_path=synthetic_geotiff_no_crs.parent / "cat.db")
    with pytest.raises(ValueError, match="validation failed"):
        pipeline.run(synthetic_geotiff_no_crs)


def test_catalog_round_trip(synthetic_geotiff_2500: Path, tmp_path: Path) -> None:
    """Tiles written to SQLite catalog should deserialize identically."""
    catalog_path = tmp_path / "tiles.db"
    pipeline = TileIngestionPipeline(
        tile_size=1024,
        overlap=64,
        catalog_path=catalog_path,
    )
    result = pipeline.run(synthetic_geotiff_2500, source_id="demo")
    assert result.tiles

    with TileCatalog(catalog_path) as catalog:
        stored = catalog.list_tiles(source_uri=result.profile.source_uri)
        assert len(stored) == len(result.tiles)
        original = result.tiles[0]
        loaded = catalog.get_tile(original.tile_id)
        assert loaded is not None
        assert loaded.tile_row == original.tile_row
        assert loaded.tile_col == original.tile_col
        assert loaded.width == original.width
        assert loaded.height == original.height
        assert loaded.crs_epsg == original.crs_epsg
        assert loaded.bbox == pytest.approx(original.bbox)


def test_streaming_reader_lazy_load(synthetic_geotiff_2500: Path) -> None:
    """Streaming reader should materialize one tile at a time."""
    profile = open_raster_profile(synthetic_geotiff_2500)
    grid = TileGrid(tile_size=1024, overlap=64)
    tiles = grid.build_tile_records(profile, source_id="stream")
    reader = StreamingTileReader(profile)

    seen_shapes: list[tuple[int, ...]] = []
    for tile_data in reader.iter_tiles(tiles[:3]):
        seen_shapes.append(tile_data.data.shape)
        assert tile_data.data.shape[1] == tile_data.data.shape[1]
        assert tile_data.crs_epsg == 32619

    assert len(seen_shapes) == 3
    assert all(shape[0] == profile.band_count for shape in seen_shapes)


def test_tile_crs_mismatch_detected(synthetic_geotiff_2500: Path) -> None:
    """Tile records with wrong CRS should fail validation."""
    profile = open_raster_profile(synthetic_geotiff_2500)
    grid = TileGrid(tile_size=1024, overlap=64)
    tile = grid.build_tile_records(profile, source_id="bad")[0]
    mismatched = replace(tile, crs_epsg=4326)
    report = validate_tile_record(
        mismatched,
        expected_crs_epsg=profile.crs_epsg,
        expected_resolution_x=profile.resolution_x,
        expected_resolution_y=profile.resolution_y,
    )
    assert not report.passed
    assert any(issue.code == "TILE_CRS_MISMATCH" for issue in report.issues)


def test_process_tile_is_stateless(synthetic_geotiff_2500: Path) -> None:
    """Pure tile task should succeed on readable synthetic tiles."""
    profile = open_raster_profile(synthetic_geotiff_2500)
    grid = TileGrid(tile_size=1024, overlap=64)
    tile = grid.build_tile_records(profile, source_id="proc")[0]
    result = process_tile(profile, tile)
    assert result.status == "ok"
    assert result.tile_id == tile.tile_id


def test_sentinel2_safe_ingestion(synthetic_sentinel2_safe: Path, tmp_path: Path) -> None:
    """Sentinel-2 SAFE layout should ingest and tile multi-band sources."""
    pipeline = TileIngestionPipeline(catalog_path=tmp_path / "s2.db")
    result = pipeline.run(synthetic_sentinel2_safe, source_id="s2")
    assert result.profile.band_count == 2
    assert len(result.tiles) >= 1

    reader = StreamingTileReader(result.profile)
    tile_data = reader.read_tile(result.tiles[0])
    assert tile_data.data.shape[0] == 2
    assert tile_data.data.dtype == np.uint16


def test_validation_audit_logging(
    synthetic_geotiff_2500: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validation summaries should be emitted for audit trails."""
    caplog.set_level(logging.INFO, logger="terra_pipeline.validation")
    pipeline = TileIngestionPipeline(catalog_path=tmp_path / "audit.db")
    pipeline.run(synthetic_geotiff_2500)
    assert any("validation_summary" in record.message for record in caplog.records)
