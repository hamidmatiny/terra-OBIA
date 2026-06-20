"""Pydantic schemas for Terra OBIA REST API requests and responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Processing lifecycle states for an OBIA job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportFormatOption(str, Enum):
    """GIS export formats available for job results."""

    GEOJSON = "geojson"
    GPKG = "gpkg"
    SHAPEFILE = "shp"


class SegmentationParams(BaseModel):
    """Segmentation configuration for a processing job."""

    backend: str = Field(
        default="classical",
        description="Segmentation backend: 'classical' (SLIC) or 'deep' (FCN-ResNet50).",
    )
    n_segments: int = Field(default=80, ge=1, description="Target superpixel count for SLIC.")
    compactness: float = Field(
        default=10.0,
        ge=0.0,
        description="SLIC compactness (higher values yield squarer superpixels).",
    )
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum softmax confidence for the deep segmentation backend.",
    )
    tile_size: int = Field(default=512, ge=64, description="Processing tile size in pixels.")
    overlap: int = Field(default=64, ge=0, description="Tile overlap in pixels for seam merge.")


class JobCreateRequest(BaseModel):
    """Request body for submitting a stand delineation processing job."""

    source_uri: str = Field(
        ...,
        description=(
            "Path or URI to input imagery (GeoTIFF/COG or Sentinel-2 SAFE directory). "
            "Local file paths are supported for on-prem deployments."
        ),
        examples=["/data/nb_forest_mosaic.tif"],
    )
    workflow: str = Field(
        default="stand_delineation",
        description="OBIA workflow identifier. Currently 'stand_delineation' is supported.",
    )
    model_id: str = Field(
        ...,
        description="Trained classification model identifier (see GET /models).",
    )
    segmentation: SegmentationParams = Field(
        default_factory=SegmentationParams,
        description="Segmentation parameters logged with results for reproducibility.",
    )
    export_formats: list[ExportFormatOption] = Field(
        default_factory=lambda: [
            ExportFormatOption.GEOJSON,
            ExportFormatOption.GPKG,
            ExportFormatOption.SHAPEFILE,
        ],
        description="GIS formats to produce when the job completes.",
    )


class JobSubmitResponse(BaseModel):
    """Response returned immediately after job submission."""

    job_id: str = Field(description="Unique job identifier for status polling.")
    status: JobStatus = Field(description="Initial job status (always 'queued').")
    message: str = Field(description="Human-readable submission confirmation.")


class JobProgress(BaseModel):
    """Progress details for long-running province-scale jobs."""

    percent: int = Field(ge=0, le=100, description="Overall completion percentage.")
    stage: str = Field(description="Current pipeline stage (ingest, segment, classify, export).")
    detail: str = Field(default="", description="Additional progress context.")


class JobStatusResponse(BaseModel):
    """Job status payload for polling."""

    job_id: str
    status: JobStatus
    workflow: str
    created_at: datetime
    updated_at: datetime
    progress: JobProgress | None = None
    error: str | None = Field(default=None, description="Error message when status is 'failed'.")


class ExportFileInfo(BaseModel):
    """Metadata for one exported GIS deliverable."""

    format: ExportFormatOption
    path: str = Field(description="Absolute path to the exported file on the server.")
    crs: str | None = Field(description="EPSG or WKT CRS preserved in the export.")


class JobResultsResponse(BaseModel):
    """Completed job results including GIS export paths."""

    job_id: str
    status: JobStatus
    object_count: int = Field(description="Number of classified stand objects produced.")
    model_id: str
    segmentation_parameters: dict[str, Any]
    exports: list[ExportFileInfo]
    summary: dict[str, Any] = Field(default_factory=dict)


class ModelSummary(BaseModel):
    """Summary of a trained classification model."""

    model_id: str
    workflow: str
    training_date: str
    training_data_description: str
    overall_accuracy: float | None = Field(
        description="Held-out object-level accuracy from training validation split."
    )
    mean_iou: float | None = Field(
        default=None,
        description="Mean polygon IoU from training validation when available.",
    )
    artifact_path: str
    accuracy_report_path: str | None = None


class ModelListResponse(BaseModel):
    """Available trained models for classification."""

    models: list[ModelSummary]
