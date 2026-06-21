"""ETL configuration and path conventions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_data_dir() -> Path:
    return Path(os.environ.get("TERRA_DATA_DIR", "data"))


@dataclass(frozen=True)
class EtlConfig:
    """Configuration for ETL output locations and CRS standards.

    Expected CRS/resolution assumptions:
        - ``standard_crs_epsg`` is the project processing CRS (default UTM 19N
          for New Brunswick forestry workflows).
        - Processed outputs land under ``{data_dir}/processed/{aoi_name}/``.
    """

    data_dir: Path = _default_data_dir()
    standard_crs_epsg: int = 32619
    ortho_filename: str = "orthoimagery.cog.tif"
    labels_filename: str = "inventory_labels.gpkg"
    training_filename: str = "training_labels.csv"
    manifest_filename: str = "manifest.json"


def processed_aoi_dir(config: EtlConfig, aoi_name: str) -> Path:
    """Return the processed output directory for an AOI."""
    return config.data_dir / "processed" / aoi_name
