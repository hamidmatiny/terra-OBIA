"""Tests for GIS export round-trip validation."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from terra_core.export import ExportFormat, export_objects, read_exported_file


@pytest.fixture
def classified_objects() -> gpd.GeoDataFrame:
    """Create classified stand objects with CRS and OBIA attributes."""
    return gpd.GeoDataFrame(
        {
            "object_id": [1, 2],
            "cover_type": ["conifer", "deciduous"],
            "canopy_closure_class": ["dense", "moderate"],
            "confidence": [0.92, 0.81],
            "area_m2": [10000.0, 8000.0],
            "perimeter_m": [400.0, 360.0],
            "compactness": [0.78, 0.75],
            "mean_band_1": [0.8, 0.4],
        },
        geometry=[box(0, 0, 100, 100), box(110, 0, 200, 100)],
        crs="EPSG:32619",
    )


@pytest.mark.parametrize("fmt", [ExportFormat.GEOJSON, ExportFormat.GPKG, ExportFormat.SHAPEFILE])
def test_export_round_trip(
    classified_objects: gpd.GeoDataFrame,
    tmp_path: Path,
    fmt: ExportFormat,
) -> None:
    """Exported files should round-trip through geopandas with CRS and attributes."""
    written = export_objects(classified_objects, tmp_path, formats=[fmt])
    loaded = read_exported_file(written[fmt.value])
    assert len(loaded) == 2
    assert loaded.crs is not None
    assert loaded.crs.to_epsg() == 32619
    assert "cover_type" in loaded.columns or "cover_type"[:10] in loaded.columns
