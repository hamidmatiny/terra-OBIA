"""Procedural synthetic AOI generator for pipeline development."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import geometry_mask, shapes
from rasterio.transform import from_origin
from shapely.geometry import shape
from skimage.transform import resize

from terra_pipeline.etl.config import EtlConfig, processed_aoi_dir
from terra_pipeline.etl.inventory_labels_etl import process_inventory_labels
from terra_pipeline.etl.orthoimagery_etl import process_orthoimagery
from terra_pipeline.etl.schema import CANOPY_CLASSES, FOREST_SUBTYPES
from terra_pipeline.etl.training_export import extract_training_dataset

logger = logging.getLogger("terra_pipeline.etl.synthetic")

CLASS_TO_INVENTORY = {0: "NF", 1: "FO", 2: "WL", 3: "WA"}
SPECTRAL_SIGNATURES: dict[str, tuple[int, int, int, int]] = {
    "NF": (1800, 1600, 1400, 900),
    "FO": (900, 1200, 1100, 3500),
    "WL": (1100, 1300, 1200, 1800),
    "WA": (600, 700, 650, 500),
}


@dataclass(frozen=True)
class SyntheticAoiResult:
    """Paths written by synthetic AOI generation."""

    aoi_name: str
    output_dir: Path
    ortho_path: Path
    labels_path: Path
    training_path: Path
    manifest_path: Path


def parse_size_metres(size: str | float | int) -> float:
    """Parse a size string like ``5km`` or ``500`` into metres."""
    if isinstance(size, int | float):
        return float(size)
    token = str(size).strip().lower()
    match = re.match(r"^([\d.]+)\s*(km|m)?$", token)
    if not match:
        msg = f"Invalid size specification: {size}"
        raise ValueError(msg)
    value = float(match.group(1))
    unit = match.group(2) or "m"
    return value * 1000.0 if unit == "km" else value


def _generate_class_mosaic(
    width: int,
    height: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Build coarse land-cover and forest-subtype mosaics."""
    coarse = max(64, min(width, height) // 8)
    noise = rng.random((coarse, coarse))
    smoothed = resize(  # type: ignore[no-untyped-call]
        noise, (coarse, coarse), order=1, preserve_range=True, anti_aliasing=True
    )
    bins = np.quantile(smoothed, [0.25, 0.5, 0.7, 0.85])
    class_coarse = np.digitize(smoothed, bins=bins).astype(np.int16)

    # Synthetic drainage channels for water.
    x = np.arange(coarse)
    channel = (np.sin(x / 8.0) * (coarse / 6.0) + coarse / 2.0).astype(int)
    for col, row_center in enumerate(channel):
        row_start = max(0, row_center - 1)
        row_end = min(coarse, row_center + 2)
        class_coarse[row_start:row_end, col] = 3

    subtype_coarse = rng.integers(0, len(FOREST_SUBTYPES), size=(coarse, coarse))
    class_fine = resize(  # type: ignore[no-untyped-call]
        class_coarse,
        (height, width),
        order=0,
        preserve_range=True,
        anti_aliasing=False,
    ).astype(np.int16)
    subtype_fine = resize(  # type: ignore[no-untyped-call]
        subtype_coarse,
        (height, width),
        order=0,
        preserve_range=True,
        anti_aliasing=False,
    ).astype(np.int16)
    subtype_fine[class_fine != 1] = -1
    return class_fine, subtype_fine


def _paint_spectral_cube(
    class_raster: np.ndarray,
    subtype_raster: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Paint RGB+NIR bands from class-appropriate spectral signatures."""
    height, width = class_raster.shape
    cube = np.zeros((4, height, width), dtype=np.uint16)
    for class_idx, inventory in CLASS_TO_INVENTORY.items():
        mask = class_raster == class_idx
        if not mask.any():
            continue
        base = np.array(SPECTRAL_SIGNATURES[inventory], dtype=np.float32)
        if inventory == "FO":
            for subtype_idx, subtype in enumerate(FOREST_SUBTYPES):
                sub_mask = mask & (subtype_raster == subtype_idx)
                if not sub_mask.any():
                    continue
                adjustment = {"conifer": 1.05, "deciduous": 0.92, "mixed": 0.98}[subtype]
                signature = base * adjustment
                noise = rng.normal(0, 80, size=(4, sub_mask.sum()))
                cube[:, sub_mask] = np.clip(signature[:, None] + noise, 200, 4000).astype(np.uint16)
        else:
            noise = rng.normal(0, 60, size=(4, mask.sum()))
            cube[:, mask] = np.clip(base[:, None] + noise, 200, 4000).astype(np.uint16)
    return cube


def _dominant_subtype(
    polygon_mask: np.ndarray,
    subtype_raster: np.ndarray,
) -> str:
    """Return the dominant forest subtype within a polygon mask."""
    values = subtype_raster[polygon_mask & (subtype_raster >= 0)]
    if values.size == 0:
        return FOREST_SUBTYPES[0]
    counts = np.bincount(values.astype(int), minlength=len(FOREST_SUBTYPES))
    return FOREST_SUBTYPES[int(np.argmax(counts))]


def _labels_from_mosaic(
    class_raster: np.ndarray,
    subtype_raster: np.ndarray,
    transform: rasterio.Affine,
    crs: CRS,
    rng: np.random.Generator,
) -> gpd.GeoDataFrame:
    """Vectorize class mosaics into inventory label polygons."""
    records: list[dict[str, object]] = []
    min_area_m2 = 400.0
    object_index = 1
    for class_idx, inventory in CLASS_TO_INVENTORY.items():
        mask = (class_raster == class_idx).astype(np.uint8)
        if not mask.any():
            continue
        for geom, value in shapes(mask, mask=mask.astype(bool), transform=transform):
            if int(value) != 1:
                continue
            polygon = shape(geom)
            if polygon.area < min_area_m2:
                continue
            local_mask = geometry_mask(
                [polygon],
                transform=transform,
                invert=True,
                out_shape=class_raster.shape,
            )
            subtype = None
            canopy = None
            if inventory == "FO":
                subtype = _dominant_subtype(local_mask, subtype_raster)
                canopy = CANOPY_CLASSES[int(rng.integers(0, len(CANOPY_CLASSES)))]
            records.append(
                {
                    "object_id": object_index,
                    "geometry": polygon,
                    "inventory_class": inventory,
                    "forest_subtype": subtype,
                    "canopy_closure_class": canopy,
                    "cover_type": subtype,
                }
            )
            object_index += 1

    if not records:
        msg = "Synthetic label generation produced no polygons."
        raise RuntimeError(msg)
    return gpd.GeoDataFrame(records, crs=crs)


def generate_synthetic_aoi(
    aoi_name: str,
    *,
    size: str | float = "1km",
    resolution_m: float = 2.0,
    origin_easting: float = 700000.0,
    origin_northing: float = 5450000.0,
    crs_epsg: int = 32619,
    seed: int = 42,
    config: EtlConfig | None = None,
    write_training: bool = True,
) -> SyntheticAoiResult:
    """Generate a synthetic orthoimagery COG and inventory labels for an AOI.

    Expected CRS/resolution assumptions:
        - Output is written to ``{TERRA_DATA_DIR}/processed/{aoi_name}/`` in
          the configured project CRS (default EPSG:32619).

    Args:
        aoi_name: AOI identifier used in output paths.
        size: AOI extent (e.g. ``5km`` or ``1000`` metres).
        resolution_m: Ground sample distance in metres.
        origin_easting: UTM easting of the upper-left origin.
        origin_northing: UTM northing of the upper-left origin.
        crs_epsg: Output CRS EPSG code.
        seed: Random seed for reproducibility.
        config: Optional ETL config override.
        write_training: When True, also export a training CSV.

    Returns:
        ``SyntheticAoiResult`` with output paths.
    """
    cfg = config or EtlConfig(standard_crs_epsg=crs_epsg)
    output_dir = processed_aoi_dir(cfg, aoi_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    size_m = parse_size_metres(size)
    width = max(32, int(size_m / resolution_m))
    height = max(32, int(size_m / resolution_m))
    rng = np.random.default_rng(seed)
    crs = CRS.from_epsg(crs_epsg)
    transform = from_origin(origin_easting, origin_northing, resolution_m, resolution_m)

    class_raster, subtype_raster = _generate_class_mosaic(width, height, rng)
    cube = _paint_spectral_cube(class_raster, subtype_raster, rng)

    raw_raster = work_dir / "orthoimagery_raw.tif"
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 4,
        "dtype": "uint16",
        "crs": crs,
        "transform": transform,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(raw_raster, "w", **profile) as dataset:
        dataset.write(cube)

    labels = _labels_from_mosaic(class_raster, subtype_raster, transform, crs, rng)
    raw_labels = work_dir / "inventory_labels_raw.gpkg"
    labels.to_file(raw_labels, driver="GPKG", layer="inventory_labels")

    ortho_path = process_orthoimagery(raw_raster, output_dir, cfg)
    _, labels_path = process_inventory_labels(raw_labels, output_dir, cfg)

    training_path = output_dir / cfg.training_filename
    if write_training:
        processed_labels = gpd.read_file(labels_path)
        extract_training_dataset(ortho_path, processed_labels, training_path)

    manifest = {
        "aoi_name": aoi_name,
        "synthetic": True,
        "size_m": size_m,
        "resolution_m": resolution_m,
        "crs_epsg": crs_epsg,
        "seed": seed,
        "outputs": {
            "orthoimagery": str(ortho_path),
            "inventory_labels": str(labels_path),
            "training_labels": str(training_path) if write_training else None,
        },
        "limitations": (
            "Synthetic data for pipeline development only. Accuracy results are "
            "not meaningful and must not be cited in sales or evaluation material."
        ),
    }
    manifest_path = output_dir / cfg.manifest_filename
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("Synthetic AOI %s written to %s", aoi_name, output_dir)

    return SyntheticAoiResult(
        aoi_name=aoi_name,
        output_dir=output_dir,
        ortho_path=ortho_path,
        labels_path=labels_path,
        training_path=training_path,
        manifest_path=manifest_path,
    )
