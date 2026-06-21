"""Validate and normalize orthoimagery rasters for training pipelines."""

from __future__ import annotations

import logging
from pathlib import Path

import rasterio
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject

from terra_pipeline.etl.config import EtlConfig
from terra_pipeline.etl.manifest import EtlManifest, ManifestEntry, ManifestStatus
from terra_pipeline.ingestion.cog_converter import CogConverter

logger = logging.getLogger("terra_pipeline.etl.orthoimagery")


def validate_raster(path: Path) -> tuple[bool, str, dict[str, object]]:
    """Open a raster and return validity, message, and metadata."""
    try:
        with rasterio.open(path) as dataset:
            if dataset.count < 1:
                return False, "Raster has no bands.", {}
            if dataset.crs is None:
                return False, "Raster is missing CRS.", {}
            meta = {
                "crs_epsg": dataset.crs.to_epsg(),
                "width": dataset.width,
                "height": dataset.height,
                "band_count": dataset.count,
                "dtype": str(dataset.dtypes[0]),
                "resolution_x": abs(dataset.res[0]),
                "resolution_y": abs(dataset.res[1]),
            }
            return True, "Raster is readable.", meta
    except rasterio.errors.RasterioIOError as exc:
        return False, f"Unreadable or corrupt raster: {exc}", {}
    except Exception as exc:  # noqa: BLE001 — surface GDAL errors to manifest
        return False, f"Raster validation failed: {exc}", {}


def _reproject_raster(
    source: Path,
    destination: Path,
    target_epsg: int,
) -> Path:
    """Reproject a raster to the project standard CRS."""
    dst_crs = CRS.from_epsg(target_epsg)
    with rasterio.open(source) as src:
        if src.crs and src.crs.to_epsg() == target_epsg:
            return source
        transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds,
        )
        profile = src.profile.copy()
        profile.update(
            {
                "crs": dst_crs,
                "transform": transform,
                "width": width,
                "height": height,
            }
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(destination, "w", **profile) as dst:
            for band_idx in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=rasterio.band(dst, band_idx),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                )
    return destination


def process_orthoimagery(
    source: Path,
    output_dir: Path,
    config: EtlConfig,
    *,
    manifest: EtlManifest | None = None,
) -> Path:
    """Validate, optionally reproject, and write a COG orthoimagery product.

    Expected CRS/resolution assumptions:
        - Output preserves source GSD unless reprojection is required for CRS
          alignment with ``config.standard_crs_epsg``.

    Args:
        source: Input GeoTIFF/COG/JP2 path.
        output_dir: Processed AOI directory.
        config: ETL configuration.
        manifest: Optional manifest to append audit entries.

    Returns:
        Path to the written COG.
    """
    valid, message, meta = validate_raster(source)
    if not valid:
        if manifest:
            manifest.add(
                ManifestEntry(
                    path=str(source),
                    asset_type="raster",
                    status=ManifestStatus.ERROR,
                    message=message,
                )
            )
        msg = message
        raise ValueError(msg)

    working = source
    target_epsg = config.standard_crs_epsg
    crs_epsg = meta.get("crs_epsg")
    if isinstance(crs_epsg, int) and crs_epsg != target_epsg:
        reprojected = output_dir / "_work" / f"{source.stem}_reproj.tif"
        working = _reproject_raster(source, reprojected, target_epsg)
        if manifest:
            manifest.add(
                ManifestEntry(
                    path=str(source),
                    asset_type="raster",
                    status=ManifestStatus.USABLE,
                    message=f"Reprojected from EPSG:{crs_epsg} to EPSG:{target_epsg}.",
                    detected_format="geotiff",
                    metadata=meta,
                )
            )
    elif manifest:
        manifest.add(
            ManifestEntry(
                path=str(source),
                asset_type="raster",
                status=ManifestStatus.USABLE,
                message=message,
                detected_format="geotiff",
                metadata=meta,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    cog_path = output_dir / config.ortho_filename
    CogConverter().convert(working, cog_path)
    logger.info("Wrote orthoimagery COG to %s", cog_path)
    return cog_path
