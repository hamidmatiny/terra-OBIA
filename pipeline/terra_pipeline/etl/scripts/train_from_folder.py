"""CLI entry point for folder-based discover → ETL → train workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from terra_core.classification.evaluation import write_accuracy_report_markdown
from terra_core.classification.models import AccuracyReport
from terra_core.classification.training import (
    TrainingConfig,
    load_labeled_dataset,
    train_stand_classifier,
)
from terra_pipeline.etl.config import EtlConfig
from terra_pipeline.etl.folder_loader import load_folder


def main() -> None:
    """Discover folder contents, run ETL, and train a stand delineation model."""
    parser = argparse.ArgumentParser(
        description=(
            "Discover mixed-format training data in a folder, validate/clean it, "
            "run ETL, and train a stand delineation classifier."
        ),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Folder containing mixed raster/vector downloads.",
    )
    parser.add_argument(
        "--aoi-name",
        required=True,
        help="AOI name for processed output under TERRA_DATA_DIR/processed/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Model artifact directory (default: models/{aoi_name}).",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override TERRA_DATA_DIR root.",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Training data description for model metadata.",
    )
    args = parser.parse_args()

    config = EtlConfig()
    if args.data_dir:
        config = EtlConfig(data_dir=Path(args.data_dir), standard_crs_epsg=config.standard_crs_epsg)

    print(f"Discovering data in {args.input_dir} …")
    result = load_folder(args.input_dir, args.aoi_name, config=config, run_etl=True)

    print(f"\nManifest: {result.manifest_path}")
    if result.ortho_path:
        print(f"  Orthoimagery: {result.ortho_path}")
    if result.labels_path:
        print(f"  Labels:       {result.labels_path}")
    if result.training_path:
        print(f"  Training CSV: {result.training_path}")

    if result.training_path is None or not result.training_path.exists():
        msg = "Training CSV was not produced — check manifest for skipped files."
        raise SystemExit(msg)

    model_dir = args.output_dir or Path("models") / args.aoi_name
    description = args.description or f"Folder ETL training data for AOI {args.aoi_name}"
    labeled = load_labeled_dataset(result.training_path)
    artifact = train_stand_classifier(
        labeled,
        TrainingConfig(training_data_description=description),
        output_dir=model_dir,
    )

    metrics = artifact.metadata.validation_metrics
    report = AccuracyReport(
        overall_accuracy=float(metrics["overall_accuracy"]),
        cover_type_metrics=metrics["cover_type_metrics"],
        canopy_closure_metrics=metrics["canopy_closure_metrics"],
        mean_iou=float(metrics.get("mean_iou", 0.0)),
        per_class_iou=metrics.get("per_class_iou", {}),
        support={str(k): int(v) for k, v in metrics.get("support", {}).items()},
    )
    report_path = model_dir / "accuracy_report.md"
    write_accuracy_report_markdown(
        report,
        report_path,
        model_id=artifact.metadata.model_id,
        training_data_description=description,
    )

    print(f"\nModel saved to {model_dir}")
    print(f"Accuracy report: {report_path}")
    print(f"Overall accuracy: {report.overall_accuracy:.1%}")


if __name__ == "__main__":
    main()
