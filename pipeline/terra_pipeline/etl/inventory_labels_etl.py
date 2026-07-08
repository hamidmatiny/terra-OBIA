"""Normalize inventory label vectors to the FO/WL/NF schema."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import CRS

from terra_pipeline.etl.config import EtlConfig
from terra_pipeline.etl.manifest import EtlManifest, ManifestEntry, ManifestStatus
from terra_pipeline.etl.schema import (
    CANOPY_CLASSES,
    CANOPY_FIELD_PATTERNS,
    COVER_TYPE_FIELD_PATTERNS,
    FOREST_SUBTYPES,
    INVENTORY_ALIASES,
    INVENTORY_CLASSES,
    INVENTORY_FIELD_PATTERNS,
)

logger = logging.getLogger("terra_pipeline.etl.inventory_labels")


def _match_column(columns: list[str], patterns: tuple[str, ...]) -> str | None:
    lowered = {col.lower(): col for col in columns}
    for pattern in patterns:
        if pattern in lowered:
            return lowered[pattern]
    for col in columns:
        normalized = re.sub(r"[^a-z0-9]", "", col.lower())
        for pattern in patterns:
            if pattern.replace("_", "") in normalized:
                return col
    return None


def detect_label_schema(columns: list[str]) -> dict[str, str | None]:
    """Detect likely inventory, cover type, and canopy columns."""
    return {
        "inventory_class": _match_column(columns, INVENTORY_FIELD_PATTERNS),
        "forest_subtype": _match_column(columns, COVER_TYPE_FIELD_PATTERNS),
        "canopy_closure_class": _match_column(columns, CANOPY_FIELD_PATTERNS),
    }


def normalize_inventory_code(value: object) -> str | None:
    """Map a raw class value to FO/WL/NF/WA."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    token = str(value).strip().upper().replace(" ", "_")
    return INVENTORY_ALIASES.get(token)


def validate_vector(path: Path) -> tuple[bool, str, dict[str, object]]:
    """Open a vector dataset and return validity, message, and metadata."""
    try:
        gdf = gpd.read_file(path)
        if gdf.empty:
            return False, "Vector dataset is empty.", {}
        if gdf.crs is None:
            return False, "Vector dataset is missing CRS.", {}
        schema = detect_label_schema(list(gdf.columns))
        meta: dict[str, object] = {
            "feature_count": len(gdf),
            "crs_epsg": gdf.crs.to_epsg(),
            "detected_schema": schema,
        }
        if schema["inventory_class"] is None and schema["forest_subtype"] is None:
            return (
                False,
                "Could not detect inventory or cover-type columns.",
                meta,
            )
        return True, "Vector is readable.", meta
    except Exception as exc:  # noqa: BLE001
        return False, f"Unreadable vector: {exc}", {}


def _normalize_labels(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize a GeoDataFrame to the unified inventory schema."""
    schema = detect_label_schema(list(gdf.columns))
    frame = gdf.copy()

    if schema["inventory_class"]:
        frame["inventory_class"] = frame[schema["inventory_class"]].map(normalize_inventory_code)
    elif schema["forest_subtype"]:
        frame["inventory_class"] = "FO"
    else:
        frame["inventory_class"] = None

    if schema["forest_subtype"]:
        frame["forest_subtype"] = (
            frame[schema["forest_subtype"]].astype(str).str.strip().str.lower()
        )
    else:
        frame["forest_subtype"] = None

    if schema["canopy_closure_class"]:
        frame["canopy_closure_class"] = (
            frame[schema["canopy_closure_class"]].astype(str).str.strip().str.lower()
        )
    else:
        frame["canopy_closure_class"] = None

    # Derive training cover_type for forest stands.
    frame["cover_type"] = frame.apply(_derive_cover_type, axis=1)
    return frame


def _derive_cover_type(row: pd.Series) -> str | None:
    inv = row.get("inventory_class")
    subtype = row.get("forest_subtype")
    if inv == "FO" and isinstance(subtype, str) and subtype in FOREST_SUBTYPES:
        return subtype
    if inv == "FO" and subtype:
        return str(subtype)
    return None


def process_inventory_labels(
    source: Path,
    output_dir: Path,
    config: EtlConfig,
    *,
    manifest: EtlManifest | None = None,
) -> tuple[gpd.GeoDataFrame, Path]:
    """Validate, reproject, and write normalized inventory labels.

    Args:
        source: Shapefile, GeoPackage, GeoJSON, or CSV-with-geometry path.
        output_dir: Processed AOI directory.
        config: ETL configuration.
        manifest: Optional manifest for audit entries.

    Returns:
        Tuple of normalized GeoDataFrame and output GeoPackage path.
    """
    valid, message, meta = validate_vector(source)
    schema_raw = meta.get("detected_schema", {})
    schema: dict[str, str | None] = schema_raw if isinstance(schema_raw, dict) else {}
    if not valid:
        if manifest:
            manifest.add(
                ManifestEntry(
                    path=str(source),
                    asset_type="vector",
                    status=ManifestStatus.ERROR,
                    message=message,
                    metadata=meta,
                )
            )
        raise ValueError(message)

    gdf = gpd.read_file(source)
    if schema.get("inventory_class") is None and schema.get("forest_subtype"):
        status = ManifestStatus.AMBIGUOUS
        note = "No inventory_class column; assuming all features are forest (FO)."
    else:
        status = ManifestStatus.USABLE
        note = message

    target_crs = CRS.from_epsg(config.standard_crs_epsg)
    if gdf.crs and gdf.crs.to_epsg() != config.standard_crs_epsg:
        gdf = gdf.to_crs(target_crs)
        note = f"{note} Reprojected to EPSG:{config.standard_crs_epsg}."

    normalized = _normalize_labels(gdf)
    invalid_classes = normalized[
        normalized["inventory_class"].notna()
        & ~normalized["inventory_class"].isin(INVENTORY_CLASSES)
    ]
    if not invalid_classes.empty and manifest:
        manifest.add(
            ManifestEntry(
                path=str(source),
                asset_type="vector",
                status=ManifestStatus.AMBIGUOUS,
                message=f"{len(invalid_classes)} features have unrecognized inventory codes.",
                metadata=meta,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / config.labels_filename
    normalized.to_file(output_path, driver="GPKG", layer="inventory_labels")
    logger.info("Wrote inventory labels to %s", output_path)

    if manifest:
        manifest.add(
            ManifestEntry(
                path=str(source),
                asset_type="vector",
                status=status,
                message=note,
                detected_format=source.suffix.lower().lstrip("."),
                metadata={**meta, "output": str(output_path)},
            )
        )
    return normalized, output_path


def forest_training_rows(labels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter to forest polygons suitable for stand delineation training."""
    forest = labels[labels["inventory_class"] == "FO"].copy()
    forest = forest[forest["cover_type"].notna()]
    valid_canopy = forest["canopy_closure_class"].isin(CANOPY_CLASSES)
    if valid_canopy.any():
        forest = forest[valid_canopy | forest["canopy_closure_class"].isna()]
    forest["canopy_closure_class"] = forest["canopy_closure_class"].fillna("moderate")
    return forest
