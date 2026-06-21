"""Training-data ETL utilities for Terra OBIA.

Synthetic AOI generation, folder-based discovery/validation, and conversion
to processed datasets compatible with stand delineation training.
"""

from terra_pipeline.etl.config import EtlConfig, processed_aoi_dir
from terra_pipeline.etl.folder_loader import FolderLoadResult, load_folder
from terra_pipeline.etl.synthetic import SyntheticAoiResult, generate_synthetic_aoi

__all__ = [
    "EtlConfig",
    "FolderLoadResult",
    "SyntheticAoiResult",
    "generate_synthetic_aoi",
    "load_folder",
    "processed_aoi_dir",
]
