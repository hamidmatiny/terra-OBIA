"""Synthetic labeled datasets for classification tests."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box


@pytest.fixture
def synthetic_labeled_csv(tmp_path: Path) -> Path:
    """Create a CSV with per-object features and stand labels."""
    rng = np.random.default_rng(0)
    rows = []
    cover_types = ["conifer", "deciduous", "mixed"]
    canopy_classes = ["sparse", "moderate", "dense"]
    for idx in range(60):
        cover = cover_types[idx % 3]
        canopy = canopy_classes[idx % 3]
        base = {"conifer": 0.8, "deciduous": 0.4, "mixed": 0.6}[cover]
        rows.append(
            {
                "object_id": idx + 1,
                "area_m2": float(rng.uniform(500, 5000)),
                "perimeter_m": float(rng.uniform(100, 400)),
                "compactness": float(rng.uniform(0.3, 0.9)),
                "mean_band_1": base + rng.normal(0, 0.05),
                "mean_band_2": base * 0.8 + rng.normal(0, 0.05),
                "mean_band_3": base * 0.6 + rng.normal(0, 0.05),
                "std_band_1": float(rng.uniform(0.01, 0.1)),
                "std_band_2": float(rng.uniform(0.01, 0.1)),
                "std_band_3": float(rng.uniform(0.01, 0.1)),
                "cover_type": cover,
                "canopy_closure_class": canopy,
            }
        )
    path = tmp_path / "labeled_stands.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture
def synthetic_segmented_objects() -> gpd.GeoDataFrame:
    """Create segmented objects resembling segmentation module output."""
    geometries = [
        box(0, 0, 100, 100),
        box(110, 0, 210, 100),
        box(0, 110, 100, 210),
    ]
    data = {
        "object_id": [1, 2, 3],
        "area_m2": [10000.0, 10000.0, 10000.0],
        "perimeter_m": [400.0, 400.0, 400.0],
        "compactness": [0.78, 0.78, 0.78],
        "mean_band_1": [0.82, 0.41, 0.58],
        "mean_band_2": [0.65, 0.33, 0.46],
        "mean_band_3": [0.50, 0.25, 0.35],
        "std_band_1": [0.05, 0.04, 0.05],
        "std_band_2": [0.04, 0.03, 0.04],
        "std_band_3": [0.03, 0.03, 0.03],
    }
    return gpd.GeoDataFrame(data, geometry=geometries, crs="EPSG:32619")


@pytest.fixture
def synthetic_reference_polygons() -> gpd.GeoDataFrame:
    """Create reference stand polygons for IoU tests."""
    geometries = [
        box(0, 0, 105, 100),
        box(105, 0, 210, 100),
        box(0, 105, 100, 210),
    ]
    data = {
        "cover_type": ["conifer", "deciduous", "mixed"],
    }
    return gpd.GeoDataFrame(data, geometry=geometries, crs="EPSG:32619")
