"""Export classified OBIA objects to standard GIS formats."""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger("terra_core.export")


class ExportFormat(str, Enum):
    """Supported GIS vector export formats."""

    GEOJSON = "geojson"
    GPKG = "gpkg"
    SHAPEFILE = "shp"


_DRIVER_MAP: dict[ExportFormat, str] = {
    ExportFormat.GEOJSON: "GeoJSON",
    ExportFormat.GPKG: "GPKG",
    ExportFormat.SHAPEFILE: "ESRI Shapefile",
}

_EXTENSION_MAP: dict[ExportFormat, str] = {
    ExportFormat.GEOJSON: ".geojson",
    ExportFormat.GPKG: ".gpkg",
    ExportFormat.SHAPEFILE: ".shp",
}


def export_objects(
    objects: gpd.GeoDataFrame,
    output_dir: Path | str,
    *,
    base_name: str = "stand_delineation",
    formats: list[ExportFormat] | None = None,
) -> dict[str, Path]:
    """Export classified objects to GIS formats preserving CRS and attributes.

    Expected CRS/resolution assumptions:
        - ``objects`` must carry a valid CRS (EPSG preferred) so ArcGIS and QGIS
          open the deliverable in the correct coordinate system.
        - Geometry and attributes describe stand objects at native GSD.

    Shapefile attribute names are shortened to 10 characters (DBF limit). Full
    attribute names are preserved in GeoJSON and GeoPackage exports.

    Args:
        objects: Classified stand objects with geometry and feature columns.
        output_dir: Directory where export files are written.
        base_name: Filename stem for each export.
        formats: Export formats to produce (defaults to all three).

    Returns:
        Mapping of format value to written file path.

    Raises:
        ValueError: When ``objects`` has no CRS defined.
    """
    if objects.empty:
        msg = "Cannot export an empty GeoDataFrame."
        raise ValueError(msg)
    if objects.crs is None:
        msg = "Export requires objects with a defined CRS."
        raise ValueError(msg)

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    selected = formats or list(ExportFormat)
    written: dict[str, Path] = {}
    clean = objects.loc[:, ~objects.columns.duplicated()].copy()

    for fmt in selected:
        export_frame = _prepare_for_format(clean, fmt)
        path = directory / f"{base_name}{_EXTENSION_MAP[fmt]}"
        target = path
        if fmt == ExportFormat.SHAPEFILE:
            target = directory / f"{base_name}.shp"

        export_frame.to_file(target, driver=_DRIVER_MAP[fmt])
        written[fmt.value] = target
        logger.info(
            json.dumps(
                {
                    "event": "gis_export",
                    "format": fmt.value,
                    "path": str(target),
                    "crs": export_frame.crs.to_string() if export_frame.crs else None,
                    "feature_count": len(export_frame),
                },
                sort_keys=True,
            )
        )
    return written


def read_exported_file(path: Path | str) -> gpd.GeoDataFrame:
    """Read an exported GIS file back into a GeoDataFrame.

    Used for round-trip validation that exports open correctly in GIS workflows.

    Args:
        path: Path to ``.geojson``, ``.gpkg``, or ``.shp`` file.

    Returns:
        GeoDataFrame with geometry and attributes.
    """
    return gpd.read_file(path)


def _prepare_for_format(objects: gpd.GeoDataFrame, fmt: ExportFormat) -> gpd.GeoDataFrame:
    """Prepare attribute columns for a specific export driver."""
    frame = objects.loc[:, ~objects.columns.duplicated()].copy()
    if fmt != ExportFormat.SHAPEFILE:
        return frame

    rename_map = {
        "canopy_closure_class": "canopy_cls",
        "needs_review": "review",
        "perimeter_m": "perim_m",
        "object_id": "obj_id",
    }
    used: set[str] = set()
    final_map: dict[str, str] = {}
    for col in frame.columns:
        if col == "geometry":
            continue
        short = rename_map.get(col, col)
        if len(short) > 10:
            short = short[:10]
        candidate = short
        suffix = 1
        while candidate in used:
            candidate = f"{short[:8]}_{suffix}"
            suffix += 1
        used.add(candidate)
        if candidate != col:
            final_map[col] = candidate
    if final_map:
        frame = frame.rename(columns=final_map)
    return frame
