"""Manifest models for folder-based ETL audit trails."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ManifestStatus(str, Enum):
    """Outcome for a discovered file or processing step."""

    USABLE = "usable"
    SKIPPED = "skipped"
    ERROR = "error"
    AMBIGUOUS = "ambiguous"


@dataclass
class ManifestEntry:
    """Single discovered or processed asset."""

    path: str
    asset_type: str
    status: ManifestStatus
    message: str
    detected_format: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EtlManifest:
    """Audit trail for folder discovery and ETL processing."""

    source: str
    aoi_name: str | None
    created_at: str
    entries: list[ManifestEntry] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)

    @classmethod
    def new(cls, source: str, aoi_name: str | None = None) -> EtlManifest:
        """Create a manifest with a UTC timestamp."""
        return cls(
            source=source,
            aoi_name=aoi_name,
            created_at=datetime.now(tz=UTC).isoformat(),
        )

    def add(self, entry: ManifestEntry) -> None:
        """Append an entry to the manifest."""
        self.entries.append(entry)

    def write_json(self, path: Path | str) -> Path:
        """Persist the manifest as JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "source": self.source,
            "aoi_name": self.aoi_name,
            "created_at": self.created_at,
            "outputs": self.outputs,
            "entries": [
                {
                    **asdict(entry),
                    "status": entry.status.value,
                }
                for entry in self.entries
            ],
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return target
