r"""Run stand classification using a registered (or direct) model artifact.

Example::

    poetry run terra-register-etl-model
    poetry run terra-predict-stands path/to/objects.gpkg \
      --model-dir models/stand_geonb_v1_balanced \
      --output predictions.gpkg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd

from terra_core.classification import ClassificationConfig, create_classifier


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict cover_type and canopy_closure_class for segmented objects.",
    )
    parser.add_argument(
        "objects",
        type=Path,
        help="GeoPackage/GeoJSON/shapefile of segmented objects with model feature columns",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="Classifier artifact directory (metadata.json + joblib files)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output GeoPackage path for enriched predictions",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for stand attribute prediction."""
    args = _parse_args(argv)
    if not args.objects.exists():
        print(f"error: objects file not found: {args.objects}", file=sys.stderr)
        return 1
    if not args.model_dir.exists():
        print(f"error: model directory not found: {args.model_dir}", file=sys.stderr)
        return 1

    objects = gpd.read_file(args.objects)
    classifier = create_classifier(
        ClassificationConfig(model_artifact_path=args.model_dir),
    )
    result = classifier.classify_objects(objects)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.objects.to_file(args.output, driver="GPKG")
    print(f"Wrote {len(result.objects)} predictions to {args.output}")
    print(f"model_id={result.model_version}")
    print(result.objects[["cover_type", "canopy_closure_class", "confidence"]].head().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
