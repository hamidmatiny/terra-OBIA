"""Accuracy metrics and human-readable evaluation reports."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from sklearn.metrics import accuracy_score, classification_report

from terra_core.classification.models import AccuracyReport


def compute_object_classification_metrics(
    y_true_cover: np.ndarray,
    y_pred_cover: np.ndarray,
    y_true_canopy: np.ndarray,
    y_pred_canopy: np.ndarray,
) -> AccuracyReport:
    """Compute object-level accuracy metrics for cover type and canopy closure.

    Args:
        y_true_cover: Ground-truth cover types.
        y_pred_cover: Predicted cover types.
        y_true_canopy: Ground-truth canopy closure classes.
        y_pred_canopy: Predicted canopy closure classes.

    Returns:
        ``AccuracyReport`` with per-class precision/recall summaries.
    """
    cover_report = classification_report(
        y_true_cover,
        y_pred_cover,
        output_dict=True,
        zero_division=0,
    )
    canopy_report = classification_report(
        y_true_canopy,
        y_pred_canopy,
        output_dict=True,
        zero_division=0,
    )

    cover_metrics = _extract_per_class_metrics(cover_report)
    canopy_metrics = _extract_per_class_metrics(canopy_report)
    combined_accuracy = float(
        np.mean(
            [
                accuracy_score(y_true_cover, y_pred_cover),
                accuracy_score(y_true_canopy, y_pred_canopy),
            ]
        )
    )
    support = {
        str(label): int(count)
        for label, count in zip(*np.unique(y_true_cover, return_counts=True), strict=False)
    }
    return AccuracyReport(
        overall_accuracy=combined_accuracy,
        cover_type_metrics=cover_metrics,
        canopy_closure_metrics=canopy_metrics,
        mean_iou=0.0,
        per_class_iou={},
        support=support,
    )


def compute_polygon_iou(
    predicted: gpd.GeoDataFrame,
    ground_truth: gpd.GeoDataFrame,
    *,
    label_column: str = "cover_type",
) -> tuple[float, dict[str, float]]:
    """Compute per-class IoU between predicted and reference stand polygons.

    Expected CRS/resolution assumptions:
        - Both GeoDataFrames share the same projected CRS (metres).
        - IoU is computed on union-of-geometries per class, suitable for
          stand-level polygon comparison against manual eCognition delineation.

    Args:
        predicted: Predicted stand objects with a class label column.
        ground_truth: Reference stand polygons with the same label column.
        label_column: Column containing thematic class labels.

    Returns:
        Tuple of ``(mean_iou, per_class_iou)``.
    """
    if predicted.crs is not None and ground_truth.crs is not None:
        ground_truth = ground_truth.to_crs(predicted.crs)

    classes = sorted(
        set(predicted[label_column].astype(str)) | set(ground_truth[label_column].astype(str))
    )
    per_class: dict[str, float] = {}
    for label in classes:
        pred_geom = unary_union(
            predicted.loc[predicted[label_column].astype(str) == label].geometry.values
        )
        ref_geom = unary_union(
            ground_truth.loc[ground_truth[label_column].astype(str) == label].geometry.values
        )
        if pred_geom.is_empty and ref_geom.is_empty:
            per_class[label] = 1.0
            continue
        if pred_geom.is_empty or ref_geom.is_empty:
            per_class[label] = 0.0
            continue
        intersection = pred_geom.intersection(ref_geom).area
        union = pred_geom.union(ref_geom).area
        per_class[label] = float(intersection / union) if union > 0 else 0.0

    mean_iou = float(np.mean(list(per_class.values()))) if per_class else 0.0
    return mean_iou, per_class


def enrich_accuracy_report_with_iou(
    report: AccuracyReport,
    predicted: gpd.GeoDataFrame,
    ground_truth: gpd.GeoDataFrame,
    *,
    label_column: str = "cover_type",
) -> AccuracyReport:
    """Add polygon IoU metrics to an existing accuracy report."""
    mean_iou, per_class_iou = compute_polygon_iou(
        predicted,
        ground_truth,
        label_column=label_column,
    )
    return AccuracyReport(
        overall_accuracy=report.overall_accuracy,
        cover_type_metrics=report.cover_type_metrics,
        canopy_closure_metrics=report.canopy_closure_metrics,
        mean_iou=mean_iou,
        per_class_iou=per_class_iou,
        support=report.support,
    )


def write_accuracy_report_markdown(
    report: AccuracyReport,
    output_path: Path | str,
    *,
    title: str = "Terra OBIA Stand Delineation Accuracy Report",
    model_id: str | None = None,
    training_data_description: str | None = None,
) -> Path:
    """Write a human-readable Markdown accuracy report for sales/audit use.

    Args:
        report: Computed accuracy metrics.
        output_path: Destination ``.md`` file path.
        title: Report heading.
        model_id: Optional model identifier for traceability.
        training_data_description: Optional training dataset summary.

    Returns:
        Path to the written report file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- **Overall accuracy (object-level):** {report.overall_accuracy:.1%}",
        f"- **Mean polygon IoU (cover type):** {report.mean_iou:.1%}",
        "",
    ]
    if model_id:
        lines.append(f"- **Model ID:** `{model_id}`")
    if training_data_description:
        lines.append(f"- **Training data:** {training_data_description}")
    lines.extend(["", "## Cover type — precision / recall / F1", ""])
    lines.extend(_format_metric_table(report.cover_type_metrics))
    lines.extend(["", "## Canopy closure — precision / recall / F1", ""])
    lines.extend(_format_metric_table(report.canopy_closure_metrics))
    if report.per_class_iou:
        lines.extend(["", "## Polygon IoU by cover type", ""])
        lines.append("| Class | IoU |")
        lines.append("|-------|-----|")
        for label, iou in sorted(report.per_class_iou.items()):
            lines.append(f"| {label} | {iou:.1%} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Higher overall accuracy indicates stronger agreement between predicted",
            "stand attributes and manual reference labels. Mean polygon IoU captures",
            "spatial agreement of stand boundaries — the primary metric for comparing",
            "against eCognition manual delineation.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _extract_per_class_metrics(report_dict: dict[str, object]) -> dict[str, dict[str, float]]:
    """Extract per-class metrics from sklearn classification_report dict."""
    metrics: dict[str, dict[str, float]] = {}
    for key, value in report_dict.items():
        if key in {"accuracy", "macro avg", "weighted avg"}:
            continue
        if isinstance(value, dict):
            metrics[str(key)] = {
                "precision": float(value.get("precision", 0.0)),
                "recall": float(value.get("recall", 0.0)),
                "f1-score": float(value.get("f1-score", 0.0)),
                "support": float(value.get("support", 0.0)),
            }
    return metrics


def _format_metric_table(metrics: dict[str, dict[str, float]]) -> list[str]:
    """Format per-class metrics as Markdown table lines."""
    lines = [
        "| Class | Precision | Recall | F1 | Support |",
        "|-------|-----------|--------|----|---------|",
    ]
    for label, values in sorted(metrics.items()):
        lines.append(
            f"| {label} | {values['precision']:.1%} | {values['recall']:.1%} | "
            f"{values['f1-score']:.1%} | {int(values['support'])} |"
        )
    return lines
