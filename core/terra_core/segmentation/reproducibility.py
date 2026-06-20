"""Reproducibility logging for segmentation jobs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


def log_segmentation_run(
    logger: logging.Logger,
    *,
    tile_id: str,
    config: dict[str, Any],
    backend: str,
) -> None:
    """Emit structured JSON log of segmentation parameters for audit trails.

    Args:
        logger: Logger instance (typically ``terra_core.segmentation``).
        tile_id: Tile identifier being processed.
        config: Serialized ``SegmentationConfig`` snapshot.
        backend: Backend name (``classical`` or ``deep``).
    """
    payload = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "event": "segmentation_run",
        "tile_id": tile_id,
        "backend": backend,
        "parameters": config,
    }
    logger.info(json.dumps(payload, sort_keys=True))
