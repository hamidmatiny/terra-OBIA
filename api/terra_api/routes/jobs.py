"""Job submission, status, and results endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from terra_api.auth import AuthenticatedKey
from terra_api.schemas import (
    JobCreateRequest,
    JobResultsResponse,
    JobStatus,
    JobStatusResponse,
    JobSubmitResponse,
)
from terra_api.services.job_runner import run_job
from terra_api.services.job_store import job_store
from terra_api.services.model_registry import resolve_model_path

router = APIRouter()


@router.post(
    "",
    response_model=JobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a stand delineation job",
    description=(
        "Queues a province-scale OBIA job: ingest and tile the input raster, "
        "segment objects, classify stand attributes, and export GIS deliverables. "
        "Poll GET /jobs/{id} for progress on long-running jobs."
    ),
)
def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    _: AuthenticatedKey,
) -> JobSubmitResponse:
    """Submit a new OBIA processing job."""
    try:
        resolve_model_path(request.model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    record = job_store.create(
        source_uri=request.source_uri,
        workflow=request.workflow,
        model_id=request.model_id,
        segmentation_params=request.segmentation.model_dump(),
        export_formats=[fmt.value for fmt in request.export_formats],
    )
    background_tasks.add_task(run_job, record.job_id)
    return JobSubmitResponse(
        job_id=record.job_id,
        status=JobStatus.QUEUED,
        message="Job accepted and queued for processing.",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
    description=(
        "Returns the current lifecycle state and progress percentage for "
        "long-running big-data jobs (queued, running, completed, failed)."
    ),
)
def get_job_status(job_id: str, _: AuthenticatedKey) -> JobStatusResponse:
    """Return job status and progress details."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        workflow=record.workflow,
        created_at=record.created_at,
        updated_at=record.updated_at,
        progress=record.to_progress(),
        error=record.error,
    )


@router.get(
    "/{job_id}/results",
    response_model=JobResultsResponse,
    summary="Retrieve completed job results",
    description=(
        "Returns classified object counts, export file paths (GeoJSON, GeoPackage, "
        "Shapefile), and processing parameters once the job has completed."
    ),
)
def get_job_results(job_id: str, _: AuthenticatedKey) -> JobResultsResponse:
    """Return GIS exports and summary statistics for a completed job."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if record.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is not complete (status={record.status.value}).",
        )
    return JobResultsResponse(
        job_id=record.job_id,
        status=record.status,
        object_count=record.object_count,
        model_id=record.model_id,
        segmentation_parameters=record.segmentation_params,
        exports=record.exports,
        summary=record.summary,
    )
