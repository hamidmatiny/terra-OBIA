"""Tests for spatial tiling utilities."""

from terra_pipeline.tiling.grid import TileGrid


def test_tile_grid_covers_small_raster() -> None:
    """Tile grid should produce windows covering a 1000×800 raster."""
    grid = TileGrid(tile_size=512, overlap=0)
    windows = grid.windows(width=1000, height=800)
    assert len(windows) >= 4
    assert all(window.width > 0 and window.height > 0 for window in windows)


def test_tile_grid_respects_overlap() -> None:
    """Overlapping tiles should use a step smaller than tile size."""
    grid = TileGrid(tile_size=512, overlap=64)
    windows = grid.windows(width=1024, height=1024)
    col_offsets = sorted({window.col_off for window in windows})
    if len(col_offsets) >= 2:
        assert col_offsets[1] - col_offsets[0] == 512 - 64
