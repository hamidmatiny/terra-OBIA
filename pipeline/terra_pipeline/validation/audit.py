"""Structured validation logging for government audit trails."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terra_pipeline.models import ValidationIssue, ValidationReport

logger = logging.getLogger("terra_pipeline.validation")


class ValidationAuditLogger:
    """Emit human-readable and JSON-structured validation logs."""

    def log_issue(self, issue: ValidationIssue) -> None:
        """Log a single validation issue at the appropriate severity."""
        payload = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "severity": issue.severity.value,
            "code": issue.code,
            "message": issue.message,
            "source_uri": issue.source_uri,
            "tile_id": issue.tile_id,
        }
        line = json.dumps(payload, sort_keys=True)
        if issue.severity.value == "error":
            logger.error(line)
        else:
            logger.warning(line)

    def log_report(self, report: ValidationReport) -> None:
        """Log all issues in a validation report."""
        summary = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "source_uri": report.source_uri,
            "passed": report.passed,
            "error_count": sum(1 for i in report.issues if i.severity.value == "error"),
            "warning_count": sum(1 for i in report.issues if i.severity.value == "warning"),
        }
        logger.info(json.dumps({"validation_summary": summary}, sort_keys=True))
        for issue in report.issues:
            self.log_issue(issue)
