"""Discover, validate, and process messy folder-based training data."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio

from terra_pipeline.etl.config import EtlConfig, processed_aoi_dir
from terra_pipeline.etl.inventory_labels_etl import process_inventory_labels, validate_vector
from terra_pipeline.etl.manifest import EtlManifest, ManifestEntry, ManifestStatus
from terra_pipeline.etl.orthoimagery_etl import process_orthoimagery, validate_raster
from terra_pipeline.etl.schema import ARCHIVE_EXTENSIONS, RASTER_EXTENSIONS, VECTOR_EXTENSIONS
from terra_pipeline.etl.training_export import extract_training_dataset

logger = logging.getLogger("terra_pipeline.etl.folder_loader")


@dataclass(frozen=True)
class FolderLoadResult:
    """Outcome of folder discovery and ETL processing."""

    aoi_name: str
    output_dir: Path
    manifest_path: Path
    ortho_path: Path | None
    labels_path: Path | None
    training_path: Path | None


def _is_raster_by_content(path: Path) -> bool:
    try:
        with rasterio.open(path):
            return True
    except Exception:  # noqa: BLE001
        return False


def _detect_vector_format(path: Path) -> bool:
    try:
        gpd.read_file(path)
        return True
    except Exception:  # noqa: BLE001
        return False


def _extract_archives(root: Path, manifest: EtlManifest, scratch: Path) -> list[Path]:
    """Extract zip archives and return expanded search roots."""
    roots = [root]
    for archive in sorted(root.rglob("*")):
        if archive.suffix.lower() not in ARCHIVE_EXTENSIONS:
            continue
        try:
            target = scratch / archive.stem
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(target)
            manifest.add(
                ManifestEntry(
                    path=str(archive),
                    asset_type="archive",
                    status=ManifestStatus.USABLE,
                    message=f"Extracted to {target}.",
                )
            )
            roots.append(target)
        except zipfile.BadZipFile:
            manifest.add(
                ManifestEntry(
                    path=str(archive),
                    asset_type="archive",
                    status=ManifestStatus.ERROR,
                    message="Corrupt or unreadable zip archive.",
                )
            )
    return roots


def _discover_files(roots: list[Path]) -> list[Path]:
    """Collect candidate files from search roots."""
    discovered: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append(path)
    return discovered


def _classify_file(path: Path, manifest: EtlManifest) -> str | None:
    """Return ``raster``, ``vector``, or None after content inspection."""
    suffix = path.suffix.lower()
    if suffix in RASTER_EXTENSIONS or _is_raster_by_content(path):
        valid, message, meta = validate_raster(path)
        manifest.add(
            ManifestEntry(
                path=str(path),
                asset_type="raster",
                status=ManifestStatus.USABLE if valid else ManifestStatus.SKIPPED,
                message=message,
                detected_format=suffix.lstrip(".") or "raster",
                metadata=meta,
            )
        )
        return "raster" if valid else None

    if suffix in VECTOR_EXTENSIONS or suffix == ".csv":
        if suffix == ".csv":
            return _classify_csv(path, manifest)
        if _detect_vector_format(path):
            valid, message, meta = validate_vector(path)
            manifest.add(
                ManifestEntry(
                    path=str(path),
                    asset_type="vector",
                    status=ManifestStatus.USABLE if valid else ManifestStatus.SKIPPED,
                    message=message,
                    detected_format=suffix.lstrip(".") or "vector",
                    metadata=meta,
                )
            )
            return "vector" if valid else None
        manifest.add(
            ManifestEntry(
                path=str(path),
                asset_type="vector",
                status=ManifestStatus.SKIPPED,
                message="File looks like vector by extension but failed to open.",
            )
        )
        return None

    if suffix in ARCHIVE_EXTENSIONS:
        return None  # handled during extraction pass

    manifest.add(
        ManifestEntry(
            path=str(path),
            asset_type="unknown",
            status=ManifestStatus.SKIPPED,
            message="Unrecognized file extension and content.",
        )
    )
    return None


def _classify_csv(path: Path, manifest: EtlManifest) -> str | None:
    """Detect CSV with WKT or lat/lon columns."""
    try:
        frame = pd.read_csv(path, nrows=5)
    except Exception as exc:  # noqa: BLE001
        manifest.add(
            ManifestEntry(
                path=str(path),
                asset_type="vector",
                status=ManifestStatus.ERROR,
                message=f"Unreadable CSV: {exc}",
            )
        )
        return None

    columns = {col.lower() for col in frame.columns}
    if "wkt" in columns or "geometry" in columns:
        manifest.add(
            ManifestEntry(
                path=str(path),
                asset_type="vector",
                status=ManifestStatus.USABLE,
                message="CSV with geometry column detected.",
                detected_format="csv",
            )
        )
        return "vector"
    lat_candidates = {"lat", "latitude", "y"}
    lon_candidates = {"lon", "long", "longitude", "x"}
    if columns & lat_candidates and columns & lon_candidates:
        manifest.add(
            ManifestEntry(
                path=str(path),
                asset_type="vector",
                status=ManifestStatus.USABLE,
                message="CSV with lat/lon columns detected.",
                detected_format="csv",
            )
        )
        return "vector"

    manifest.add(
        ManifestEntry(
            path=str(path),
            asset_type="vector",
            status=ManifestStatus.SKIPPED,
            message="CSV missing geometry, WKT, or lat/lon columns.",
        )
    )
    return None


def _csv_to_geodataframe(path: Path) -> gpd.GeoDataFrame:
    """Convert CSV with WKT or lat/lon to GeoDataFrame."""
    frame = pd.read_csv(path)
    lowered = {col.lower(): col for col in frame.columns}
    if "wkt" in lowered:
        from shapely import wkt

        geometry = frame[lowered["wkt"]].map(wkt.loads)
        return gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")
    if "geometry" in lowered:
        from shapely import wkt

        geometry = frame[lowered["geometry"]].map(wkt.loads)
        return gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")
    lat_col = next((lowered[c] for c in ("lat", "latitude", "y") if c in lowered), None)
    lon_col = next((lowered[c] for c in ("lon", "long", "longitude", "x") if c in lowered), None)
    if lat_col and lon_col:
        return gpd.GeoDataFrame(
            frame,
            geometry=gpd.points_from_xy(frame[lon_col], frame[lat_col]),
            crs="EPSG:4326",
        )
    msg = f"CSV {path} has no usable geometry columns."
    raise ValueError(msg)


def load_folder(
    input_dir: Path | str,
    aoi_name: str,
    *,
    config: EtlConfig | None = None,
    run_etl: bool = True,
) -> FolderLoadResult:
    """Discover and optionally process all usable assets in a folder.

    Args:
        input_dir: Root folder containing mixed downloads.
        aoi_name: AOI name for processed output paths.
        config: Optional ETL configuration.
        run_etl: When True, write processed COG/labels/training outputs.

    Returns:
        ``FolderLoadResult`` with manifest and output paths.
    """
    cfg = config or EtlConfig()
    root = Path(input_dir)
    if not root.is_dir():
        msg = f"Input directory does not exist: {root}"
        raise FileNotFoundError(msg)

    output_dir = processed_aoi_dir(cfg, aoi_name)
    manifest = EtlManifest.new(source=str(root.resolve()), aoi_name=aoi_name)

    with tempfile.TemporaryDirectory(prefix="terra_etl_") as scratch_name:
        scratch = Path(scratch_name)
        search_roots = _extract_archives(root, manifest, scratch)
        candidates = _discover_files(search_roots)

        raster_paths: list[Path] = []
        vector_paths: list[Path] = []
        for candidate in candidates:
            kind = _classify_file(candidate, manifest)
            if kind == "raster":
                raster_paths.append(candidate)
            elif kind == "vector":
                vector_paths.append(candidate)

    ortho_path: Path | None = None
    labels_path: Path | None = None
    training_path: Path | None = None

    if run_etl:
        if raster_paths:
            ortho_path = process_orthoimagery(raster_paths[0], output_dir, cfg, manifest=manifest)
            manifest.outputs["orthoimagery"] = str(ortho_path)
            for extra in raster_paths[1:]:
                manifest.add(
                    ManifestEntry(
                        path=str(extra),
                        asset_type="raster",
                        status=ManifestStatus.SKIPPED,
                        message="Additional raster ignored; first usable raster selected.",
                    )
                )
        else:
            manifest.add(
                ManifestEntry(
                    path=str(root),
                    asset_type="folder",
                    status=ManifestStatus.ERROR,
                    message="No usable raster found.",
                )
            )

        if vector_paths:
            vector_source = vector_paths[0]
            if vector_source.suffix.lower() == ".csv":
                csv_gdf = _csv_to_geodataframe(vector_source)
                csv_gpkg = output_dir / "_work" / "csv_import.gpkg"
                csv_gpkg.parent.mkdir(parents=True, exist_ok=True)
                csv_gdf.to_file(csv_gpkg, driver="GPKG")
                vector_source = csv_gpkg
            _, labels_path = process_inventory_labels(
                vector_source,
                output_dir,
                cfg,
                manifest=manifest,
            )
            manifest.outputs["inventory_labels"] = str(labels_path)
            for extra in vector_paths[1:]:
                manifest.add(
                    ManifestEntry(
                        path=str(extra),
                        asset_type="vector",
                        status=ManifestStatus.SKIPPED,
                        message="Additional vector ignored; first usable vector selected.",
                    )
                )
        else:
            manifest.add(
                ManifestEntry(
                    path=str(root),
                    asset_type="folder",
                    status=ManifestStatus.ERROR,
                    message="No usable vector labels found.",
                )
            )

        if ortho_path and labels_path:
            labels = gpd.read_file(labels_path)
            training_path = output_dir / cfg.training_filename
            extract_training_dataset(ortho_path, labels, training_path)
            manifest.outputs["training_labels"] = str(training_path)

    manifest_path = output_dir / cfg.manifest_filename
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest.write_json(manifest_path)
    logger.info("Folder load manifest written to %s", manifest_path)

    return FolderLoadResult(
        aoi_name=aoi_name,
        output_dir=output_dir,
        manifest_path=manifest_path,
        ortho_path=ortho_path,
        labels_path=labels_path,
        training_path=training_path,
    )
