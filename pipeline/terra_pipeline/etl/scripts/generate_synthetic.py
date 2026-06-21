"""CLI entry point for synthetic AOI generation."""

from __future__ import annotations

import argparse

from terra_pipeline.etl.config import EtlConfig
from terra_pipeline.etl.synthetic import generate_synthetic_aoi


def main() -> None:
    """Generate a synthetic AOI for pipeline development."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate a synthetic orthoimagery COG and inventory labels for "
            "pipeline development and testing."
        ),
    )
    parser.add_argument("--name", required=True, help="AOI name (output folder).")
    parser.add_argument(
        "--size",
        default="5km",
        help="AOI extent, e.g. 5km or 1000 (metres). Default: 5km.",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=2.0,
        help="Ground sample distance in metres. Default: 2.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override TERRA_DATA_DIR root (default: env or ./data).",
    )
    parser.add_argument(
        "--no-training-csv",
        action="store_true",
        help="Skip writing training_labels.csv.",
    )
    args = parser.parse_args()

    config = EtlConfig()
    if args.data_dir:
        from pathlib import Path

        config = EtlConfig(data_dir=Path(args.data_dir), standard_crs_epsg=config.standard_crs_epsg)

    result = generate_synthetic_aoi(
        args.name,
        size=args.size,
        resolution_m=args.resolution,
        seed=args.seed,
        config=config,
        write_training=not args.no_training_csv,
    )
    print(f"Synthetic AOI written to {result.output_dir}")
    print(f"  Orthoimagery: {result.ortho_path}")
    print(f"  Labels:       {result.labels_path}")
    if not args.no_training_csv:
        print(f"  Training CSV: {result.training_path}")
    print(f"  Manifest:     {result.manifest_path}")
    print(
        "\nNote: Synthetic data is for pipeline development only — accuracy "
        "results are not meaningful and must not be cited in sales or evaluation material."
    )


if __name__ == "__main__":
    main()
