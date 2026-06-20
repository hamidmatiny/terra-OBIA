"""Job submission and status endpoints (scaffolding)."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class JobCreateRequest(BaseModel):
    """Request body for submitting an OBIA processing job."""

    source_uri: str = Field(..., description="URI to the source COG (s3://, file://, etc.)")
    workflow: str = Field(
        ...,
        description="Workflow identifier, e.g. 'forestry_stand_delineation'",
    )


class JobResponse(BaseModel):
    """Response returned after job submission."""

    job_id: str
    status: str


@router.post("", response_model=JobResponse, status_code=202)
def create_job(request: JobCreateRequest) -> JobResponse:
    """Submit a new OBIA processing job.

    Processing is not yet implemented; this endpoint validates the request
    shape and returns a placeholder job identifier.
    """
    return JobResponse(job_id="placeholder", status="accepted")
