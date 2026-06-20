"""Feature extraction from segmented object GeoDataFrames."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

DEFAULT_FEATURE_COLUMNS: tuple[str, ...] = (
    "area_m2",
    "perimeter_m",
    "compactness",
)


def infer_feature_columns(objects: gpd.GeoDataFrame | pd.DataFrame) -> list[str]:
    """Detect numeric feature columns from a segmentation GeoDataFrame.

    Expected CRS/resolution assumptions:
        - Spectral columns follow ``mean_*`` and ``std_*`` naming from
          ``terra_core.segmentation.vectorize``.

    Args:
        objects: Segmented objects with attribute columns.

    Returns:
        Ordered list of numeric column names suitable for sklearn models.
    """
    spectral = sorted(
        col
        for col in objects.columns
        if col.startswith("mean_") or col.startswith("std_")
    )
    shape_cols = [col for col in DEFAULT_FEATURE_COLUMNS if col in objects.columns]
    return shape_cols + spectral


def objects_to_feature_matrix(
    objects: gpd.GeoDataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    """Convert object attributes to a numeric feature matrix.

    Args:
        objects: Segmented objects GeoDataFrame.
        feature_columns: Column names to include as model inputs.

    Returns:
        Array with shape ``(n_objects, n_features)``.

    Raises:
        KeyError: When a requested feature column is missing.
    """
    matrix = objects[feature_columns].astype(float).to_numpy()
    return np.nan_to_num(matrix, nan=0.0)  # type: ignore[no-any-return]


def labeled_frame_to_features(
    labeled: pd.DataFrame | gpd.GeoDataFrame,
    *,
    feature_columns: list[str] | None = None,
    cover_type_column: str = "cover_type",
    canopy_closure_column: str = "canopy_closure_class",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Extract features and labels from a labeled training dataset.

    Expected CRS/resolution assumptions:
        - Training rows contain per-object features at native GSD; geometry is
          optional for CSV inputs but required for spatial IoU evaluation.

    Args:
        labeled: Labeled objects with feature and target columns.
        feature_columns: Optional explicit feature list; inferred when omitted.
        cover_type_column: Ground-truth dominant cover type column.
        canopy_closure_column: Ground-truth canopy closure class column.

    Returns:
        Tuple of ``(X, y_cover, y_canopy, feature_columns)``.
    """
    if feature_columns is None:
        feature_columns = infer_feature_columns(labeled)

    x_matrix = labeled[feature_columns].astype(float).to_numpy()
    x_matrix = np.nan_to_num(x_matrix, nan=0.0)
    y_cover = labeled[cover_type_column].astype(str).to_numpy()
    y_canopy = labeled[canopy_closure_column].astype(str).to_numpy()
    return x_matrix, y_cover, y_canopy, feature_columns
