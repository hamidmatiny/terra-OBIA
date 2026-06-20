"""Raster ingestion from COG, GeoTIFF, and Sentinel-2 SAFE products."""

from terra_pipeline.ingestion.cog_converter import CogConverter
from terra_pipeline.ingestion.detector import detect_raster_format
from terra_pipeline.ingestion.reader import open_raster_profile
from terra_pipeline.ingestion.sentinel2 import discover_sentinel2_bands, profile_from_sentinel2

__all__ = [
    "CogConverter",
    "detect_raster_format",
    "discover_sentinel2_bands",
    "open_raster_profile",
    "profile_from_sentinel2",
]
