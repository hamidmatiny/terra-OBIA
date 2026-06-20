"""Coordinate end-to-end OBIA job execution across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle states for an OBIA processing job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobRunner:
    """Orchestrate ingestion → segmentation → classification → export.

    The runner wires together pipeline stages without embedding algorithm
    details. Each stage communicates through well-defined interfaces so that
    workflows like wetland classification can swap classification models while
    reusing the same tiling and export paths.
    """

    def submit(self, source_uri: str, workflow: str) -> str:
        """Enqueue a new job and return its identifier.

        Args:
            source_uri: URI to the source imagery (expected to be or become a COG).
            workflow: Named workflow configuration to execute.

        Returns:
            Unique job identifier.

        Raises:
            NotImplementedError: Placeholder until orchestration backend lands.
        """
        raise NotImplementedError("Job orchestration is not yet implemented.")
