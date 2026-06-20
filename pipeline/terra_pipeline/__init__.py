"""Terra OBIA data pipeline.

Handles raw imagery ingestion, COG conversion, spatial tiling, and job
orchestration. This package coordinates I/O and scheduling; segmentation and
classification logic lives in ``terra_core``.
"""

from terra_pipeline.ingest import IngestionResult, TileIngestionPipeline
from terra_pipeline.models import (
    RasterFormat,
    RasterProfile,
    TileData,
    TileRecord,
    ValidationIssue,
    ValidationReport,
)
from terra_pipeline.processing import process_tile, read_tile_for_processing
from terra_pipeline.tiling import StreamingTileReader, TileCatalog, TileGrid

__all__ = [
    "IngestionResult",
    "RasterFormat",
    "RasterProfile",
    "StreamingTileReader",
    "TileCatalog",
    "TileData",
    "TileGrid",
    "TileIngestionPipeline",
    "TileRecord",
    "ValidationIssue",
    "ValidationReport",
    "process_tile",
    "read_tile_for_processing",
]

__version__ = "0.1.0"
