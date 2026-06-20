"""Stateless tile task functions designed for Dask/Ray parallelization.

Each function accepts all inputs explicitly and does not mutate shared state,
making it suitable for ``dask.delayed`` or ``ray.remote`` wrappers in future
work without code changes.
"""

from __future__ import annotations

from terra_pipeline.models import (
    RasterProfile,
    TileData,
    TileProcessingResult,
    TileRecord,
)
from terra_pipeline.tiling.streaming import StreamingTileReader


def read_tile_for_processing(profile: RasterProfile, tile: TileRecord) -> TileData:
    """Read a single tile for downstream OBIA stages.

    Expected CRS/resolution assumptions:
        - ``profile`` and ``tile`` describe the same source URI and native CRS.
        - Output array GSD matches ``profile.resolution_x/y``.

    This function is pure with respect to pipeline state: it creates a local
    reader, materializes one tile, and returns. Distributed executors can map
    this function across tile records independently.

    Args:
        profile: Validated parent raster profile.
        tile: Catalog tile metadata.

    Returns:
        In-memory tile payload.
    """
    reader = StreamingTileReader(profile)
    return reader.read_tile(tile)


def process_tile(profile: RasterProfile, tile: TileRecord) -> TileProcessingResult:
    """Process one tile through the OBIA pipeline stub.

    Expected CRS/resolution assumptions:
        - Tile pixels are in the source CRS at native resolution.

    Future segmentation/classification stages will plug in here. The function
    intentionally remains stateless so orchestrators can schedule one invocation
    per tile on Dask or Ray clusters.

    Args:
        profile: Validated parent raster profile.
        tile: Catalog tile metadata.

    Returns:
        Processing result with status metadata (no side effects).
    """
    reader = StreamingTileReader(profile)
    if not reader.verify_tile_readable(tile):
        return TileProcessingResult(
            tile_id=tile.tile_id,
            status="failed",
            message="Tile window is unreadable or corrupt.",
        )

    tile_data = reader.read_tile(tile)
    if tile_data.data.size == 0:
        return TileProcessingResult(
            tile_id=tile.tile_id,
            status="skipped",
            message="Tile window produced empty array.",
        )

    return TileProcessingResult(
        tile_id=tile.tile_id,
        status="ok",
        message=f"Read {tile_data.data.shape} array at native GSD.",
    )
