"""Validate raster sources and tile metadata before processing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import CRS

from terra_pipeline.models import ValidationIssue, ValidationReport, ValidationSeverity

if TYPE_CHECKING:
    from terra_pipeline.models import RasterProfile, TileRecord


def validate_raster_profile(profile: RasterProfile) -> ValidationReport:
    """Validate a raster profile prior to tiling.

    Expected CRS/resolution assumptions:
        - Validation checks the source as stored on disk; no reprojection is
          attempted.
        - Resolution tolerance is 1e-6 CRS units for float comparisons.

    Args:
        profile: Metadata extracted from the source raster.

    Returns:
        Validation report with errors and warnings suitable for audit logging.
    """
    report = ValidationReport(source_uri=profile.source_uri)

    if profile.crs_epsg is None and profile.crs_wkt is None:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="CRS_MISSING",
                message="Raster has no CRS definition.",
                source_uri=profile.source_uri,
            )
        )

    if profile.width <= 0 or profile.height <= 0:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="INVALID_DIMENSIONS",
                message=f"Invalid raster dimensions: {profile.width}x{profile.height}.",
                source_uri=profile.source_uri,
            )
        )

    if profile.band_count <= 0:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="NO_BANDS",
                message="Raster reports zero bands.",
                source_uri=profile.source_uri,
            )
        )

    if profile.resolution_x <= 0 or profile.resolution_y <= 0:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="INVALID_RESOLUTION",
                message=(
                    f"Non-positive resolution: x={profile.resolution_x}, "
                    f"y={profile.resolution_y}."
                ),
                source_uri=profile.source_uri,
            )
        )

    if profile.nodata is None:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="NODATA_UNDEFINED",
                message="NoData value is not defined; masked pixels may be misclassified.",
                source_uri=profile.source_uri,
            )
        )

    if profile.format.value == "cog" and not profile.is_tiled:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="COG_NOT_TILED",
                message="File detected as COG but internal tiling flag is unset.",
                source_uri=profile.source_uri,
            )
        )

    return report


def validate_tile_record(
    tile: TileRecord,
    *,
    expected_crs_epsg: int | None,
    expected_resolution_x: float,
    expected_resolution_y: float,
    resolution_tolerance: float = 1e-6,
) -> ValidationReport:
    """Validate a catalog tile against its parent source metadata.

    Expected CRS/resolution assumptions:
        - ``expected_crs_epsg`` and resolution values come from the parent
          ``RasterProfile`` of the same ingestion job.
        - Mismatches are flagged as errors before tiles enter ML processing.

    Args:
        tile: Tile metadata record from the catalog.
        expected_crs_epsg: EPSG code of the parent source (may be None).
        expected_resolution_x: Parent pixel width in CRS units.
        expected_resolution_y: Parent pixel height in CRS units.
        resolution_tolerance: Absolute tolerance for resolution comparison.

    Returns:
        Validation report for the tile.
    """
    report = ValidationReport(source_uri=tile.source_uri)

    if tile.width <= 0 or tile.height <= 0:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="TILE_INVALID_DIMENSIONS",
                message=f"Tile {tile.tile_id} has invalid dimensions.",
                source_uri=tile.source_uri,
                tile_id=tile.tile_id,
            )
        )

    if expected_crs_epsg is not None and tile.crs_epsg != expected_crs_epsg:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="TILE_CRS_MISMATCH",
                message=(
                    f"Tile CRS EPSG:{tile.crs_epsg} does not match source "
                    f"EPSG:{expected_crs_epsg}."
                ),
                source_uri=tile.source_uri,
                tile_id=tile.tile_id,
            )
        )

    if abs(tile.resolution_x - expected_resolution_x) > resolution_tolerance:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="TILE_RESOLUTION_MISMATCH",
                message=(
                    f"Tile resolution_x {tile.resolution_x} != " f"source {expected_resolution_x}."
                ),
                source_uri=tile.source_uri,
                tile_id=tile.tile_id,
            )
        )

    if abs(tile.resolution_y - expected_resolution_y) > resolution_tolerance:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="TILE_RESOLUTION_MISMATCH",
                message=(
                    f"Tile resolution_y {tile.resolution_y} != " f"source {expected_resolution_y}."
                ),
                source_uri=tile.source_uri,
                tile_id=tile.tile_id,
            )
        )

    if tile.crs_wkt is not None and expected_crs_epsg is not None:
        try:
            tile_crs = CRS.from_epsg(tile.crs_epsg) if tile.crs_epsg else CRS.from_wkt(tile.crs_wkt)
            source_crs = CRS.from_epsg(expected_crs_epsg)
            if tile_crs != source_crs:
                report.add(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="TILE_CRS_WKT_MISMATCH",
                        message=f"Tile {tile.tile_id} CRS WKT differs from source CRS.",
                        source_uri=tile.source_uri,
                        tile_id=tile.tile_id,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - validation must capture CRS parse failures
            report.add(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="TILE_CRS_PARSE_ERROR",
                    message=f"Unable to parse tile CRS: {exc}",
                    source_uri=tile.source_uri,
                    tile_id=tile.tile_id,
                )
            )

    return report


def validate_band_crs_consistency(
    source_uri: str,
    band_profiles: list[RasterProfile],
) -> ValidationReport:
    """Ensure all bands in a multi-file source share CRS and resolution.

    Expected CRS/resolution assumptions:
        - All ``band_profiles`` describe bands intended to be stacked for one
          mosaic; EPSG and resolution must match exactly.

    Args:
        source_uri: Logical source identifier for logging.
        band_profiles: One profile per band file.

    Returns:
        Validation report flagging inconsistent bands.
    """
    report = ValidationReport(source_uri=source_uri)
    if not band_profiles:
        report.add(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="NO_BAND_PROFILES",
                message="No band profiles supplied for CRS consistency check.",
                source_uri=source_uri,
            )
        )
        return report

    reference = band_profiles[0]
    for band in band_profiles[1:]:
        if band.crs_epsg != reference.crs_epsg:
            report.add(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="BAND_CRS_MISMATCH",
                    message=(
                        f"Band {band.source_uri} CRS EPSG:{band.crs_epsg} != "
                        f"reference EPSG:{reference.crs_epsg}."
                    ),
                    source_uri=source_uri,
                )
            )
        if band.width != reference.width or band.height != reference.height:
            report.add(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="BAND_DIMENSION_MISMATCH",
                    message=(
                        f"Band {band.source_uri} dimensions "
                        f"{band.width}x{band.height} != reference "
                        f"{reference.width}x{reference.height}."
                    ),
                    source_uri=source_uri,
                )
            )
        if (
            abs(band.resolution_x - reference.resolution_x) > 1e-6
            or abs(band.resolution_y - reference.resolution_y) > 1e-6
        ):
            report.add(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="BAND_RESOLUTION_MISMATCH",
                    message=f"Band {band.source_uri} resolution differs from reference.",
                    source_uri=source_uri,
                )
            )
    return report
