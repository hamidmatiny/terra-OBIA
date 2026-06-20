"""Sentinel-2 SAFE/JP2 band discovery and profile extraction."""

from __future__ import annotations

import re
from pathlib import Path

import rasterio

from terra_pipeline.models import RasterFormat, RasterProfile

_BAND_NAME_PATTERN = re.compile(r"_B(?P<band>\d{2})_(?P<res>\d+)m", re.IGNORECASE)


def discover_sentinel2_bands(safe_path: Path | str, *, resolution_m: int = 10) -> list[Path]:
    """Discover JP2 band files inside a Sentinel-2 SAFE product.

    Expected CRS/resolution assumptions:
        - Bands are selected from ``IMG_DATA/*_R{resolution}m/`` folders.
        - All returned bands share the same CRS and pixel grid at the chosen
          resolution (typically UTM, 10 m for R10m bands).

    Args:
        safe_path: Path to the ``.SAFE`` directory.
        resolution_m: Target ground resolution in metres (10, 20, or 60).

    Returns:
        Sorted list of JP2 paths for the requested resolution.

    Raises:
        FileNotFoundError: When no matching JP2 bands are found.
    """
    root = Path(safe_path)
    resolution_tag = f"R{resolution_m}m"
    candidates = sorted(set(root.rglob("*.jp2")) | set(root.rglob("*.tif")))
    bands: list[tuple[str, Path]] = []

    for candidate in candidates:
        if resolution_tag not in candidate.as_posix():
            continue
        match = _BAND_NAME_PATTERN.search(candidate.name)
        if match is None:
            continue
        bands.append((match.group("band"), candidate))

    if not bands:
        msg = f"No Sentinel-2 JP2 bands at {resolution_m}m found under {root}"
        raise FileNotFoundError(msg)

    bands.sort(key=lambda item: item[0])
    return [path for _, path in bands]


def profile_from_sentinel2(
    safe_path: Path | str,
    *,
    resolution_m: int = 10,
) -> RasterProfile:
    """Build a multi-band ``RasterProfile`` from Sentinel-2 JP2 bands.

    Expected CRS/resolution assumptions:
        - Uses the first discovered band for georeferencing metadata.
        - All bands at the chosen resolution must share dimensions and CRS.

    Args:
        safe_path: Path to the ``.SAFE`` directory.
        resolution_m: Band resolution folder to read (default 10 m).

    Returns:
        Combined profile referencing all band paths in ``band_uris``.
    """
    root = Path(safe_path)
    band_paths = discover_sentinel2_bands(root, resolution_m=resolution_m)
    profiles = [_profile_from_single_band(path) for path in band_paths]
    reference = profiles[0]

    for band_profile in profiles[1:]:
        if band_profile.crs_epsg != reference.crs_epsg:
            msg = "Sentinel-2 bands have inconsistent CRS."
            raise ValueError(msg)
        if band_profile.width != reference.width or band_profile.height != reference.height:
            msg = "Sentinel-2 bands have inconsistent dimensions."
            raise ValueError(msg)

    return RasterProfile(
        source_uri=str(root),
        format=RasterFormat.SENTINEL2_SAFE,
        crs_epsg=reference.crs_epsg,
        crs_wkt=reference.crs_wkt,
        width=reference.width,
        height=reference.height,
        band_count=len(band_paths),
        dtype=reference.dtype,
        transform=reference.transform,
        resolution_x=reference.resolution_x,
        resolution_y=reference.resolution_y,
        nodata=reference.nodata,
        is_tiled=False,
        band_uris=tuple(str(p) for p in band_paths),
    )


def profile_from_band_file(path: Path | str) -> RasterProfile:
    """Extract profile metadata from a single Sentinel-2 JP2 band file."""
    return _profile_from_single_band(Path(path))


def _profile_from_single_band(path: Path) -> RasterProfile:
    """Extract profile metadata from a single JP2 band."""
    with rasterio.open(path) as dataset:
        crs_epsg = dataset.crs.to_epsg() if dataset.crs else None
        transform = dataset.transform
        res_x, res_y = dataset.res
        return RasterProfile(
            source_uri=str(path),
            format=RasterFormat.SENTINEL2_SAFE,
            crs_epsg=crs_epsg,
            crs_wkt=dataset.crs.to_wkt() if dataset.crs else None,
            width=dataset.width,
            height=dataset.height,
            band_count=dataset.count,
            dtype=str(dataset.dtypes[0]),
            transform=transform,
            resolution_x=abs(res_x),
            resolution_y=abs(res_y),
            nodata=dataset.nodatavals[0] if dataset.nodatavals else None,
            is_tiled=bool(dataset.profile.get("tiled")),
            band_uris=(str(path),),
        )
