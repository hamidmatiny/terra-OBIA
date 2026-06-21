"""Tests for folder-based ETL discovery and manifest reporting."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from shapely.geometry import box

from terra_pipeline.etl.config import EtlConfig
from terra_pipeline.etl.folder_loader import load_folder
from terra_pipeline.etl.synthetic import generate_synthetic_aoi


def _write_valid_raster(path: Path) -> None:
    transform = from_origin(700100.0, 5449900.0, 2.0, 2.0)
    data = np.random.default_rng(1).integers(500, 3000, size=(4, 200, 200), dtype=np.uint16)
    profile = {
        "driver": "GTiff",
        "height": 200,
        "width": 200,
        "count": 4,
        "dtype": "uint16",
        "crs": CRS.from_epsg(32619),
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(data)


def _write_valid_labels(path: Path) -> None:
    gdf = gpd.GeoDataFrame(
        {
            "inventory_class": ["FO", "FO", "WL"],
            "cover_type": ["conifer", "deciduous", "wetland"],
            "canopy_closure_class": ["dense", "moderate", "sparse"],
        },
        geometry=[
            box(700100, 5449700, 700200, 5449800),
            box(700250, 5449700, 700400, 5449850),
            box(700100, 5449850, 700300, 5449900),
        ],
        crs="EPSG:32619",
    )
    gdf.to_file(path, driver="GPKG")


@pytest.fixture
def messy_folder(tmp_path: Path) -> Path:
    """Build a folder with valid, corrupt, and misnamed assets."""
    root = tmp_path / "messy_downloads"
    root.mkdir()

    _write_valid_raster(root / "ortho.tif")
    _write_valid_labels(root / "labels.gpkg")

    # Misnamed but valid raster (content sniffing).
    _write_valid_raster(root / "backup_ortho.dat")

    # Corrupt raster.
    (root / "broken.tif").write_bytes(b"not-a-geotiff")

    # Unknown text file.
    (root / "readme.txt").write_text("Field notes", encoding="utf-8")

    # Zip containing another valid raster (should be extracted and logged).
    zip_path = root / "extra.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        raster_in_zip = tmp_path / "zortho.tif"
        _write_valid_raster(raster_in_zip)
        archive.write(raster_in_zip, arcname="zortho.tif")

    # Corrupt zip.
    (root / "bad.zip").write_bytes(b"PK\x0304corrupt")

    return root


def test_folder_loader_detects_usable_and_skipped_files(messy_folder: Path, tmp_path: Path) -> None:
    """Folder loader processes valid assets and reports skips/errors in manifest."""
    config = EtlConfig(data_dir=tmp_path / "data")
    result = load_folder(messy_folder, "messy_aoi", config=config, run_etl=True)

    assert result.manifest_path.exists()
    assert result.ortho_path is not None and result.ortho_path.exists()
    assert result.labels_path is not None and result.labels_path.exists()
    assert result.training_path is not None and result.training_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    statuses = {entry["status"] for entry in manifest["entries"]}
    assert "usable" in statuses
    assert "skipped" in statuses
    assert "error" in statuses

    messages = " ".join(entry["message"] for entry in manifest["entries"])
    assert "corrupt" in messages.lower() or "unreadable" in messages.lower()


def test_folder_loader_misnamed_raster_detected(
    messy_folder: Path,
    tmp_path: Path,
) -> None:
    """Misnamed raster with valid content appears as usable in manifest."""
    config = EtlConfig(data_dir=tmp_path / "data")
    result = load_folder(messy_folder, "messy_aoi2", config=config, run_etl=False)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    dat_entries = [entry for entry in manifest["entries"] if entry["path"].endswith(".dat")]
    assert any(entry["status"] == "usable" for entry in dat_entries)


def test_train_from_folder_integration(tmp_path: Path) -> None:
    """End-to-end folder load using synthetic assets produces training CSV."""
    config = EtlConfig(data_dir=tmp_path / "data")
    synthetic = generate_synthetic_aoi(
        "source_aoi",
        size="400",
        resolution_m=4.0,
        seed=3,
        config=config,
    )

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    import shutil

    shutil.copy(synthetic.ortho_path, input_dir / "ortho.tif")
    shutil.copy(synthetic.labels_path, input_dir / "labels.gpkg")

    result = load_folder(input_dir, "trained_aoi", config=config, run_etl=True)
    assert result.training_path is not None
    assert result.training_path.stat().st_size > 0
