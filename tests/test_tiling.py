"""Tests for spatial tiling utilities."""

from terra_pipeline.ingestion.reader import open_raster_profile
from terra_pipeline.tiling.grid import TileGrid


def test_tile_grid_default_size_and_overlap() -> None:
    """Default grid should be 1024 px with 64 px overlap."""
    grid = TileGrid()
    assert grid.tile_size == 1024
    assert grid.overlap == 64


def test_tile_grid_step_math() -> None:
    """Overlapping tiles should advance by tile_size minus overlap."""
    grid = TileGrid(tile_size=1024, overlap=64)
    specs = grid.window_specs(width=2048, height=2048)
    col_offsets = sorted({spec.col_off for spec in specs})
    assert col_offsets[0] == 0
    assert col_offsets[1] - col_offsets[0] == 1024 - 64
    assert col_offsets[-1] + 1024 >= 2048


def test_tile_grid_edge_tiles_are_smaller() -> None:
    """Edge tiles should shrink when extent is not an exact multiple."""
    grid = TileGrid(tile_size=1024, overlap=64)
    specs = grid.window_specs(width=2500, height=2100)
    max_col = max(spec.col_off for spec in specs)
    edge = next(spec for spec in specs if spec.col_off == max_col)
    assert edge.width == 2500 - max_col
    assert edge.width < 1024
    assert edge.width > 0


def test_tile_grid_covers_full_extent() -> None:
    """Union of tile windows should cover the full raster extent."""
    grid = TileGrid(tile_size=1024, overlap=64)
    width, height = 2500, 2100
    specs = grid.window_specs(width=width, height=height)
    covered = [[False] * width for _ in range(height)]
    for spec in specs:
        for row in range(spec.row_off, spec.row_off + spec.height):
            for col in range(spec.col_off, spec.col_off + spec.width):
                covered[row][col] = True
    assert all(all(row) for row in covered)


def test_build_tile_records_includes_geotransform(
    synthetic_geotiff_2500,
) -> None:
    """Tile records should carry affine transform and bbox metadata."""
    profile = open_raster_profile(synthetic_geotiff_2500)
    grid = TileGrid(tile_size=1024, overlap=64)
    records = grid.build_tile_records(profile, source_id="test")
    assert records
    first = records[0]
    assert first.transform is not None
    assert len(first.bbox) == 4
    assert first.crs_epsg == 32619
    assert first.tile_id.startswith("test_")
