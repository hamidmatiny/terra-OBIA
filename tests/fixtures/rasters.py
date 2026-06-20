"""Synthetic raster fixtures for pipeline tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin


@pytest.fixture
def synthetic_geotiff_2500(tmp_path: Path) -> Path:
    """Create a 2500×2100 uint16 GeoTIFF with EPSG:32619 (UTM 19N).

    Expected CRS/resolution assumptions:
        - 10 m GSD, suitable for tiling tests with 1024 px windows and overlap.
    """
    path = tmp_path / "synthetic_2500.tif"
    width, height = 2500, 2100
    transform = from_origin(500000.0, 5500000.0, 10.0, 10.0)
    data = np.arange(width * height, dtype=np.uint16).reshape(height, width)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint16",
        "crs": CRS.from_epsg(32619),
        "transform": transform,
        "nodata": 0,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(data, 1)
    return path


@pytest.fixture
def synthetic_geotiff_no_crs(tmp_path: Path) -> Path:
    """Create a GeoTIFF without CRS for validation failure tests."""
    path = tmp_path / "no_crs.tif"
    width, height = 512, 512
    transform = from_origin(0.0, 5120.0, 10.0, 10.0)
    data = np.ones((height, width), dtype=np.uint8)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(data, 1)
    return path


@pytest.fixture
def synthetic_sentinel2_safe(tmp_path: Path) -> Path:
    """Create a minimal Sentinel-2 SAFE layout with two 10 m JP2 bands.

    Expected CRS/resolution assumptions:
        - EPSG:32619 at 10 m GSD, 1200×1000 pixels per band.
    """
    safe_dir = tmp_path / "S2A_TEST.SAFE"
    img_dir = safe_dir / "GRANULE" / "L2A_T19TCJ_A012345_20240101T154321" / "IMG_DATA" / "R10m"
    img_dir.mkdir(parents=True)

    width, height = 1200, 1000
    transform = from_origin(600000.0, 5400000.0, 10.0, 10.0)
    crs = CRS.from_epsg(32619)

    for band_name in ("B02_10m", "B03_10m"):
        band_path = img_dir / f"T19TCJ_20240101T154321_{band_name}.tif"
        data = (np.random.default_rng(42).integers(0, 1000, size=(height, width))).astype(np.uint16)
        profile = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": 1,
            "dtype": "uint16",
            "crs": crs,
            "transform": transform,
            "nodata": 0,
        }
        with rasterio.open(band_path, "w", **profile) as dataset:
            dataset.write(data, 1)

    return safe_dir
