"""CLI entry point for training stand delineation classifiers."""

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


def main() -> None:
    """Train a stand delineation classifier and write an accuracy report."""
    parser = argparse.ArgumentParser(
        description="Train a Terra OBIA stand delineation classifier on labeled data.",
    )
    parser.add_argument(
        "labeled_data",
        type=Path,
        help="Path to labeled CSV or GeoPackage with stand attributes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for the versioned model artifact.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional Markdown accuracy report output path.",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="Labeled stand polygon dataset",
        help="Human-readable training data description for audit metadata.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.25,
        help="Held-out validation fraction.",
    )
    args = parser.parse_args()

    labeled = load_labeled_dataset(args.labeled_data)
    config = TrainingConfig(
        training_data_description=args.description,
        test_size=args.test_size,
    )
    artifact = train_stand_classifier(labeled, config, output_dir=args.output_dir)

    metrics = artifact.metadata.validation_metrics
    report = AccuracyReport(
        overall_accuracy=float(metrics["overall_accuracy"]),
        cover_type_metrics=metrics["cover_type_metrics"],
        canopy_closure_metrics=metrics["canopy_closure_metrics"],
        mean_iou=float(metrics.get("mean_iou", 0.0)),
        per_class_iou=metrics.get("per_class_iou", {}),
        support={str(k): int(v) for k, v in metrics.get("support", {}).items()},
    )

    report_path = args.report_path or (args.output_dir / "accuracy_report.md")
    write_accuracy_report_markdown(
        report,
        report_path,
        model_id=artifact.metadata.model_id,
        training_data_description=config.training_data_description,
    )
    print(f"Model saved to {args.output_dir}")
    print(f"Accuracy report written to {report_path}")


if __name__ == "__main__":
    main()
