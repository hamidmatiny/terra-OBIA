"""Vectorize label rasters into GeoDataFrames with object features."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
from numpy.typing import NDArray
from rasterio import features
from rasterio.transform import Affine
from shapely.geometry import Polygon, shape

from terra_core.segmentation.features import shape_metrics, spectral_stats_for_object
from terra_core.segmentation.models import ObjectFeatures


def vectorize_labels(
    label_raster: NDArray[np.int32],
    data: NDArray[np.floating],
    transform: Affine,
    *,
    crs_wkt: str | None,
    band_names: tuple[str, ...],
    min_object_area_px: int = 16,
    pixel_area_m2: float | None = None,
) -> gpd.GeoDataFrame:
    """Convert a label raster to polygons with eCognition-style attributes.

    Expected CRS/resolution assumptions:
        - ``label_raster`` and ``data`` share the same pixel grid and GSD.
        - ``transform`` georeferences the label raster origin.
        - ``pixel_area_m2`` when provided overrides geometry.area for sanity
          checks in tests; otherwise area comes from shapely geometry.

    Args:
        label_raster: Integer labels ``(height, width)``; 0 is background.
        data: Spectral array ``(bands, height, width)`` at native resolution.
        transform: Affine transform for the label raster.
        crs_wkt: WKT string for the output GeoDataFrame CRS.
        band_names: Names used for spectral statistic columns.
        min_object_area_px: Minimum pixel count to keep an object.
        pixel_area_m2: Optional constant pixel area for metric computation.

    Returns:
        GeoDataFrame with geometry and object feature columns.
    """
    rows: list[dict[str, object]] = []
    for geom, value in features.shapes(
        label_raster.astype(np.int32),
        transform=transform,
        connectivity=8,
    ):
        object_id = int(value)
        if object_id == 0:
            continue
        mask = label_raster == object_id
        if int(np.count_nonzero(mask)) < min_object_area_px:
            continue

        polygon = shape(geom)
        if polygon.is_empty or not isinstance(polygon, Polygon):
            continue

        area_m2, perimeter_m, compact = shape_metrics(polygon)
        if pixel_area_m2 is not None:
            area_m2 = float(np.count_nonzero(mask)) * pixel_area_m2

        means, stds = spectral_stats_for_object(data, mask, band_names)
        feature = ObjectFeatures(
            object_id=object_id,
            area_m2=area_m2,
            perimeter_m=perimeter_m,
            compactness=compact,
            band_means=means,
            band_stds=stds,
        )
        row: dict[str, object] = {
            "object_id": feature.object_id,
            "area_m2": feature.area_m2,
            "perimeter_m": feature.perimeter_m,
            "compactness": feature.compactness,
            "geometry": polygon,
        }
        for key, val in feature.band_means.items():
            row[f"mean_{key}"] = val
        for key, val in feature.band_stds.items():
            row[f"std_{key}"] = val
        rows.append(row)

    if not rows:
        return gpd.GeoDataFrame(
            columns=[
                "object_id",
                "area_m2",
                "perimeter_m",
                "compactness",
                "geometry",
            ],
            geometry="geometry",
            crs=crs_wkt,
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs_wkt)
    return gdf
