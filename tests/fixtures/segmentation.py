"""Synthetic imagery fixtures for segmentation tests."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def rgb_tile_array() -> np.ndarray:
    """Create a 256×256 3-band float32 tile with distinct rectangular regions.

    Expected CRS/resolution assumptions:
        - Values are dimensionless reflectance used only for segmentation tests.
    """
    data = np.zeros((3, 256, 256), dtype=np.float32)
    data[:, 20:120, 20:120] = 0.2
    data[:, 20:120, 140:240] = 0.5
    data[:, 140:240, 20:240] = 0.8
    return data


@pytest.fixture
def two_tile_mosaic() -> tuple[np.ndarray, int]:
    """Build a 512×256 mosaic and overlap value for merge tests.

    Returns:
        Tuple of ``(full_array, overlap_px)`` where ``full_array`` has shape
        ``(3, 256, 512)``.
    """
    overlap = 64
    full = np.zeros((3, 256, 512), dtype=np.float32)
    full[:, :, :256] = 0.3
    full[:, :, 256:] = 0.7
    # Shared seam gradient in overlap for realistic boundary
    seam_start = 256 - overlap
    for col in range(seam_start, 256):
        blend = (col - seam_start) / overlap
        full[:, :, col] = 0.3 * (1 - blend) + 0.7 * blend
    return full, overlap


def split_mosaic_into_tiles(
    full_array: np.ndarray,
    *,
    overlap: int,
    tile_size: int = 256,
) -> list[tuple[np.ndarray, int, int, int, int]]:
    """Split a mosaic into overlapping tile arrays with offsets.

    Returns:
        List of ``(data, tile_row, tile_col, col_off, row_off)`` tuples.
    """
    _, height, width = full_array.shape
    step = tile_size - overlap
    tiles: list[tuple[np.ndarray, int, int, int, int]] = []
    row_indices = list(range(0, height, step))
    for tile_row, row_off in enumerate(row_indices):
        col_indices = list(range(0, width, step))
        for tile_col, col_off in enumerate(col_indices):
            win_w = min(tile_size, width - col_off)
            win_h = min(tile_size, height - row_off)
            tile = full_array[:, row_off : row_off + win_h, col_off : col_off + win_w]
            tiles.append((tile, tile_row, tile_col, col_off, row_off))
    return tiles
