"""Pure, stateless tile processing primitives for local and distributed execution."""

from terra_pipeline.processing.tile_task import process_tile, read_tile_for_processing

__all__ = ["process_tile", "read_tile_for_processing"]
