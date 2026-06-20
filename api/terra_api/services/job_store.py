"""In-memory job state store for API job lifecycle management."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from terra_api.schemas import ExportFileInfo, JobProgress, JobStatus


class JobStage(str, Enum):
    """Pipeline stages used for progress reporting."""

    QUEUED = "queued"
    INGEST = "ingest"
    SEGMENT = "segment"
    MERGE = "merge"
    CLASSIFY = "classify"
    EXPORT = "export"
    DONE = "done"


@dataclass
class JobRecord:
    """Internal job state tracked by the API."""

    job_id: str
    source_uri: str
    workflow: str
    model_id: str
    segmentation_params: dict[str, Any]
    export_formats: list[str]
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage = JobStage.QUEUED
    progress_percent: int = 0
    progress_detail: str = "Waiting to start"
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    error: str | None = None
    output_dir: str | None = None
    exports: list[ExportFileInfo] = field(default_factory=list)
    object_count: int = 0
    summary: dict[str, Any] = field(default_factory=dict)

    def to_progress(self) -> JobProgress | None:
        """Return progress when job is active or complete."""
        if self.status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED}:
            return JobProgress(
                percent=self.progress_percent,
                stage=self.stage.value,
                detail=self.progress_detail,
            )
        return None


class JobStore:
    """Thread-safe in-memory job registry."""

    def __init__(self) -> None:
        """Initialize an empty job store."""
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        source_uri: str,
        workflow: str,
        model_id: str,
        segmentation_params: dict[str, Any],
        export_formats: list[str],
    ) -> JobRecord:
        """Create and register a new queued job."""
        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            source_uri=source_uri,
            workflow=workflow,
            model_id=model_id,
            segmentation_params=segmentation_params,
            export_formats=export_formats,
        )
        with self._lock:
            self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        """Fetch a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields: object) -> JobRecord | None:
        """Update job fields and refresh ``updated_at``."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            for key, value in fields.items():
                setattr(record, key, value)
            record.updated_at = datetime.now(tz=UTC)
            return record


job_store = JobStore()
