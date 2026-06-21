"""Extract per-object training features from orthoimagery and inventory labels."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry.base import BaseGeometry

from terra_core.classification.features import infer_feature_columns
from terra_core.segmentation.features import shape_metrics
from terra_pipeline.etl.inventory_labels_etl import forest_training_rows
from terra_pipeline.etl.schema import BAND_NAMES_RGBN

logger = logging.getLogger("terra_pipeline.etl.training_export")


def _band_stats(
    data: np.ndarray,
    mask: np.ndarray,
    band_names: tuple[str, ...],
) -> dict[str, float]:
    """Compute mean and std for each band inside a boolean mask."""
    stats: dict[str, float] = {}
    for idx in range(data.shape[0]):
        name = band_names[idx] if idx < len(band_names) else f"band_{idx + 1}"
        values = data[idx][mask]
        if values.size == 0:
            stats[f"mean_{name}"] = 0.0
            stats[f"std_{name}"] = 0.0
        else:
            stats[f"mean_{name}"] = float(np.mean(values))
            stats[f"std_{name}"] = float(np.std(values))
    return stats


def extract_training_dataset(
    raster_path: Path | str,
    labels: gpd.GeoDataFrame,
    output_path: Path | str,
    *,
    forest_only: bool = True,
) -> Path:
    """Sample raster bands per label polygon and write a training CSV.

    Expected CRS/resolution assumptions:
        - ``labels`` geometry CRS matches the raster CRS.
        - Output rows include shape metrics and ``mean_*`` / ``std_*`` spectral
          columns compatible with ``train_stand_classifier``.

    Args:
        raster_path: Orthoimagery COG/GeoTIFF path.
        labels: Normalized inventory labels GeoDataFrame.
        output_path: Destination CSV path.
        forest_only: When True, export only FO polygons with cover types.

    Returns:
        Path to the written CSV.
    """
    target = Path(output_path)
    rows = labels if not forest_only else forest_training_rows(labels)
    if rows.empty:
        msg = "No forest training polygons available after filtering."
        raise ValueError(msg)

    records: list[dict[str, object]] = []
    with rasterio.open(raster_path) as dataset:
        band_names = BAND_NAMES_RGBN[: dataset.count]
        for object_id, (_, row) in enumerate(rows.iterrows(), start=1):
            geometry = row.geometry
            if not isinstance(geometry, BaseGeometry) or geometry.is_empty:
                continue
            mask = geometry_mask(
                [geometry],
                transform=dataset.transform,
                invert=True,
                out_shape=(dataset.height, dataset.width),
            )
            window = dataset.window(*geometry.bounds)
            data = dataset.read(window=window)
            local_mask = mask[
                int(window.row_off) : int(window.row_off + window.height),
                int(window.col_off) : int(window.col_off + window.width),
            ]
            if not local_mask.any():
                continue
            area, perimeter, compact = shape_metrics(geometry)  # type: ignore[arg-type]
            spectral = _band_stats(data, local_mask, band_names)
            records.append(
                {
                    "object_id": object_id,
                    "area_m2": area,
                    "perimeter_m": perimeter,
                    "compactness": compact,
                    **spectral,
                    "cover_type": row.get("cover_type"),
                    "canopy_closure_class": row.get("canopy_closure_class", "moderate"),
                    "inventory_class": row.get("inventory_class"),
                }
            )

    if not records:
        msg = "Could not sample any polygons from the raster extent."
        raise ValueError(msg)

    frame = pd.DataFrame(records)
    feature_columns = infer_feature_columns(frame)
    ordered = [
        "object_id",
        *feature_columns,
        "cover_type",
        "canopy_closure_class",
        "inventory_class",
    ]
    frame = frame[[col for col in ordered if col in frame.columns]]
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    logger.info("Wrote training dataset with %d rows to %s", len(frame), target)
    return target
