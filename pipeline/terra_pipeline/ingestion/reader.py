"""Unified raster opening for COG, GeoTIFF, and Sentinel-2 sources."""

from __future__ import annotations

from pathlib import Path

import rasterio

from terra_pipeline.ingestion.detector import detect_raster_format
from terra_pipeline.ingestion.sentinel2 import profile_from_sentinel2
from terra_pipeline.models import RasterFormat, RasterProfile


def open_raster_profile(path: Path | str) -> RasterProfile:
    """Open a supported raster source and return geospatial metadata only.

    Expected CRS/resolution assumptions:
        - Returns native CRS and GSD from the source without resampling.
        - For Sentinel-2 SAFE products, uses 10 m bands by default.

    Args:
        path: Path to GeoTIFF/COG or Sentinel-2 ``.SAFE`` directory.

    Returns:
        ``RasterProfile`` suitable for validation and tiling.
    """
    source = Path(path)
    fmt = detect_raster_format(source)

    if fmt == RasterFormat.SENTINEL2_SAFE:
        return profile_from_sentinel2(source)

    return _profile_from_geotiff(source, fmt)


def _profile_from_geotiff(path: Path, fmt: RasterFormat) -> RasterProfile:
    """Extract profile metadata from a GeoTIFF or COG file."""
    with rasterio.open(path) as dataset:
        crs_epsg = dataset.crs.to_epsg() if dataset.crs else None
        res_x, res_y = dataset.res
        is_tiled = bool(dataset.profile.get("tiled") or dataset.profile.get("layout") == "COG")
        return RasterProfile(
            source_uri=str(path),
            format=fmt,
            crs_epsg=crs_epsg,
            crs_wkt=dataset.crs.to_wkt() if dataset.crs else None,
            width=dataset.width,
            height=dataset.height,
            band_count=dataset.count,
            dtype=str(dataset.dtypes[0]),
            transform=dataset.transform,
            resolution_x=abs(res_x),
            resolution_y=abs(res_y),
            nodata=dataset.nodatavals[0] if dataset.nodatavals else None,
            is_tiled=is_tiled,
            band_uris=(str(path),),
        )
