"""Tests for synthetic AOI generation."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import box

from terra_pipeline.etl.config import EtlConfig
from terra_pipeline.etl.synthetic import generate_synthetic_aoi, parse_size_metres


def test_parse_size_metres() -> None:
    """Size parser accepts km and metre inputs."""
    assert parse_size_metres("5km") == 5000.0
    assert parse_size_metres("500") == 500.0
    assert parse_size_metres(2.5) == 2.5


def test_generate_synthetic_aoi_outputs_are_valid(tmp_path: Path) -> None:
    """Synthetic AOI produces readable COG, labels, and training CSV."""
    config = EtlConfig(data_dir=tmp_path)
    result = generate_synthetic_aoi(
        "test_aoi",
        size="500",
        resolution_m=5.0,
        seed=7,
        config=config,
    )

    assert result.ortho_path.exists()
    assert result.labels_path.exists()
    assert result.training_path.exists()
    assert result.manifest_path.exists()

    with rasterio.open(result.ortho_path) as dataset:
        assert dataset.count == 4
        assert dataset.crs is not None
        assert dataset.read(1).max() > 0

    labels = gpd.read_file(result.labels_path)
    assert not labels.empty
    assert "inventory_class" in labels.columns
    assert set(labels["inventory_class"].dropna()).issubset({"FO", "WL", "NF", "WA"})

    training = pd.read_csv(result.training_path)
    assert len(training) >= 1
    assert "cover_type" in training.columns
    assert "mean_band_1" in training.columns


def test_synthetic_labels_overlap_raster_extent(tmp_path: Path) -> None:
    """Label polygons intersect the orthoimagery extent."""
    config = EtlConfig(data_dir=tmp_path)
    result = generate_synthetic_aoi(
        "overlap_aoi",
        size="500",
        resolution_m=5.0,
        seed=7,
        config=config,
    )

    labels = gpd.read_file(result.labels_path)
    with rasterio.open(result.ortho_path) as dataset:
        raster_bounds = box(*dataset.bounds)
        overlap = labels[labels.intersects(raster_bounds)]
        assert len(overlap) == len(labels)

        # At least one forest polygon samples valid pixels.
        forest = labels[labels["inventory_class"] == "FO"].iloc[0]
        mask = geometry_mask(
            [forest.geometry],
            transform=dataset.transform,
            invert=True,
            out_shape=(dataset.height, dataset.width),
        )
        assert mask.any()


def test_generate_synthetic_aoi_invalid_size() -> None:
    """Invalid size strings raise ValueError."""
    with pytest.raises(ValueError, match="Invalid size"):
        parse_size_metres("not-a-size")
