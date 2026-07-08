"""Review, correction, and export download endpoints."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from terra_api.auth import AuthenticatedKey
from terra_api.schemas import (
    CorrectionRequest,
    CorrectionResponse,
    ExportFormatOption,
    FeatureCollectionResponse,
    JobApproveRequest,
    JobApproveResponse,
    JobStatus,
)
from terra_api.services.job_store import job_store
from terra_api.services.review import apply_correction, list_corrections, load_features_geojson

router = APIRouter()


@router.get(
    "/{job_id}/features",
    response_model=FeatureCollectionResponse,
    summary="Get stand polygons for map display",
    description=(
        "Returns GeoJSON features with classification attributes and any analyst "
        "corrections applied. Used by the review dashboard map viewer."
    ),
)
def get_job_features(job_id: str, _: AuthenticatedKey) -> FeatureCollectionResponse:
    """Return GeoJSON features for a completed job."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if record.status != JobStatus.COMPLETED or record.output_dir is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Features available only for completed jobs.",
        )
    try:
        geojson = load_features_geojson(record.output_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FeatureCollectionResponse(
        type=geojson.get("type", "FeatureCollection"),
        features=geojson.get("features", []),
        crs=geojson.get("crs"),
    )


@router.post(
    "/{job_id}/corrections",
    response_model=CorrectionResponse,
    summary="Submit a manual classification correction",
    description=(
        "Logs an analyst override for audit and future model retraining. "
        "Corrections are appended to corrections.jsonl in the job output directory."
    ),
)
def submit_correction(
    job_id: str,
    request: CorrectionRequest,
    _: AuthenticatedKey,
) -> CorrectionResponse:
    """Apply and log a manual classification correction."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if record.status != JobStatus.COMPLETED or record.output_dir is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Corrections require a completed job.",
        )
    try:
        updated = apply_correction(
            record.output_dir,
            object_id=request.object_id,
            cover_type=request.cover_type,
            canopy_closure_class=request.canopy_closure_class,
            analyst_id=request.analyst_id,
            reason=request.reason,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CorrectionResponse(**updated)


@router.get(
    "/{job_id}/corrections",
    summary="List logged corrections for a job",
    description="Returns all analyst corrections logged for audit and training data export.",
)
def get_corrections(job_id: str, _: AuthenticatedKey) -> list[dict[str, object]]:
    """List correction audit records."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if record.output_dir is None:
        return []
    return list_corrections(record.output_dir)


@router.post(
    "/{job_id}/approve",
    response_model=JobApproveResponse,
    summary="Approve reviewed job results",
    description="Marks a job as analyst-approved after review and any corrections.",
)
def approve_job(
    job_id: str,
    request: JobApproveRequest,
    _: AuthenticatedKey,
) -> JobApproveResponse:
    """Record analyst approval of job deliverables."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if record.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed jobs can be approved.",
        )
    approved_at = datetime.now(tz=UTC)
    job_store.update(
        job_id,
        approved=True,
        approved_by=request.analyst_id,
        approved_at=approved_at,
    )
    if record.output_dir:
        approval_path = Path(record.output_dir) / "approval.json"
        approval_path.write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "approved_by": request.analyst_id,
                    "approved_at": approved_at.isoformat(),
                    "notes": request.notes,
                    "correction_count": len(list_corrections(record.output_dir)),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return JobApproveResponse(
        job_id=job_id,
        approved=True,
        approved_by=request.analyst_id,
        approved_at=approved_at.isoformat(),
    )


@router.get(
    "/{job_id}/exports/{export_format}",
    summary="Download a GIS export file",
    description="Download Shapefile (zip), GeoPackage, or GeoJSON deliverable.",
    response_class=FileResponse,
)
def download_export(
    job_id: str,
    export_format: ExportFormatOption,
    _: AuthenticatedKey,
) -> FileResponse:
    """Download an export file for a completed job."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if record.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exports available only for completed jobs.",
        )

    export_match = next(
        (item for item in record.exports if item.format == export_format),
        None,
    )
    if export_match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export format '{export_format.value}' not found for this job.",
        )

    path = Path(export_match.path)
    if export_format == ExportFormatOption.SHAPEFILE:
        zip_path = path.parent / "stand_delineation_shp.zip"
        if not zip_path.exists():
            with zipfile.ZipFile(zip_path, "w") as archive:
                for sibling in path.parent.glob("stand_delineation.*"):
                    archive.write(sibling, arcname=sibling.name)
        return FileResponse(
            zip_path,
            filename="stand_delineation.zip",
            media_type="application/zip",
        )

    media_types = {
        ExportFormatOption.GEOJSON: "application/geo+json",
        ExportFormatOption.GPKG: "application/geopackage+sqlite3",
    }
    return FileResponse(
        path,
        filename=path.name,
        media_type=media_types.get(export_format, "application/octet-stream"),
    )
