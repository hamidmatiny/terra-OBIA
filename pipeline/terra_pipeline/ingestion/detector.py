"""Detect raster source formats for pipeline ingestion."""

from __future__ import annotations

from pathlib import Path

from terra_pipeline.models import RasterFormat


def detect_raster_format(path: Path | str) -> RasterFormat:
    """Detect the raster format of a local path.

    Expected CRS/resolution assumptions:
        - Detection is based on file layout only; CRS is validated after open.

    Args:
        path: Path to a GeoTIFF/COG file or Sentinel-2 ``.SAFE`` directory.

    Returns:
        Detected ``RasterFormat``.

    Raises:
        FileNotFoundError: When ``path`` does not exist.
        ValueError: When the format is not supported.
    """
    source = Path(path)
    if not source.exists():
        msg = f"Source path does not exist: {source}"
        raise FileNotFoundError(msg)

    if source.is_dir() and source.suffix.upper() == ".SAFE":
        return RasterFormat.SENTINEL2_SAFE

    if source.is_dir() and any(source.rglob("*.jp2")):
        return RasterFormat.SENTINEL2_SAFE

    if source.is_dir() and any(source.rglob("*.tif")):
        return RasterFormat.SENTINEL2_SAFE

    if source.suffix.lower() in {".tif", ".tiff", ".geotiff"}:
        if _is_cog(source):
            return RasterFormat.COG
        return RasterFormat.GEOTIFF

    msg = f"Unsupported raster source: {source}"
    raise ValueError(msg)


def _is_cog(path: Path) -> bool:
    """Return True when rasterio reports COG layout flags."""
    import rasterio

    with rasterio.open(path) as dataset:
        return bool(dataset.profile.get("layout") == "COG" or dataset.overviews(1))
