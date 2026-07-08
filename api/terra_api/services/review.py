"""Persist analyst corrections for audit and future model training."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd

logger = logging.getLogger("terra_api.review")


def load_features_geojson(job_output_dir: Path | str) -> dict[str, Any]:
    """Load stand delineation GeoJSON for map display.

    Expected CRS/resolution assumptions:
        - GeoJSON coordinates are in the source CRS used during processing.

    Args:
        job_output_dir: Job output directory containing ``exports/``.

    Returns:
        GeoJSON FeatureCollection dictionary with corrections applied.
    """
    output = Path(job_output_dir)
    reviewed = output / "review" / "stand_delineation.geojson"
    base = output / "exports" / "stand_delineation.geojson"
    source = reviewed if reviewed.exists() else base
    if not source.exists():
        msg = f"GeoJSON export not found for job at {output}"
        raise FileNotFoundError(msg)
    payload: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    return payload


def apply_correction(
    job_output_dir: Path | str,
    *,
    object_id: int,
    cover_type: str,
    canopy_closure_class: str,
    analyst_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Apply a manual classification override and log it for training data.

    Corrections are appended to ``corrections.jsonl`` in the job output directory.
    Each record captures the original and corrected values, analyst identity,
    and timestamp — suitable for future model retraining (see ``docs/dashboard.md``).

    Args:
        job_output_dir: Job output directory.
        object_id: Segment object identifier.
        cover_type: Corrected dominant cover type.
        canopy_closure_class: Corrected canopy closure class.
        analyst_id: Analyst username or ID for audit trail.
        reason: Optional review note.

    Returns:
        Updated feature properties for the corrected object.
    """
    output = Path(job_output_dir)
    base_path = output / "exports" / "stand_delineation.geojson"
    if not base_path.exists():
        msg = "Job exports not found; cannot apply correction."
        raise FileNotFoundError(msg)

    gdf = gpd.read_file(base_path)
    if "object_id" not in gdf.columns:
        msg = "Export missing object_id column."
        raise ValueError(msg)

    mask = gdf["object_id"] == object_id
    if not mask.any():
        msg = f"Object {object_id} not found in job results."
        raise ValueError(msg)

    row = gdf.loc[mask].iloc[0]
    correction_record = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "object_id": object_id,
        "analyst_id": analyst_id,
        "reason": reason,
        "original": {
            "cover_type": str(row.get("cover_type", "")),
            "canopy_closure_class": str(row.get("canopy_closure_class", "")),
            "confidence": float(row.get("confidence", 0.0))
            if row.get("confidence") is not None
            else None,
        },
        "corrected": {
            "cover_type": cover_type,
            "canopy_closure_class": canopy_closure_class,
        },
    }

    corrections_path = output / "corrections.jsonl"
    with corrections_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(correction_record, sort_keys=True) + "\n")

    gdf.loc[mask, "cover_type"] = cover_type
    gdf.loc[mask, "canopy_closure_class"] = canopy_closure_class
    gdf.loc[mask, "confidence"] = 1.0
    gdf.loc[mask, "needs_review"] = False
    gdf.loc[mask, "manual_override"] = True
    gdf.loc[mask, "corrected_by"] = analyst_id
    gdf.loc[mask, "corrected_at"] = correction_record["timestamp"]

    review_dir = output / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    reviewed_path = review_dir / "stand_delineation.geojson"
    gdf.to_file(reviewed_path, driver="GeoJSON")

    logger.info(
        json.dumps(
            {
                "event": "classification_correction",
                "job_output_dir": str(output),
                **correction_record,
            },
            sort_keys=True,
        )
    )
    updated = gdf.loc[mask].iloc[0]
    return {
        "object_id": object_id,
        "cover_type": str(updated["cover_type"]),
        "canopy_closure_class": str(updated["canopy_closure_class"]),
        "confidence": float(updated["confidence"]),
        "manual_override": True,
        "corrected_by": analyst_id,
        "corrected_at": correction_record["timestamp"],
    }


def list_corrections(job_output_dir: Path | str) -> list[dict[str, Any]]:
    """Return all logged corrections for a job."""
    path = Path(job_output_dir) / "corrections.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records
