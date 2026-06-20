"""End-to-end ingestion and tiling pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from terra_pipeline.ingestion.reader import open_raster_profile
from terra_pipeline.models import (
    RasterProfile,
    TileRecord,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from terra_pipeline.tiling.catalog import TileCatalog
from terra_pipeline.tiling.grid import TileGrid
from terra_pipeline.tiling.streaming import StreamingTileReader
from terra_pipeline.validation.audit import ValidationAuditLogger
from terra_pipeline.validation.raster import (
    validate_band_crs_consistency,
    validate_raster_profile,
    validate_tile_record,
)


@dataclass
class IngestionResult:
    """Outcome of an ingestion and tiling run."""

    profile: RasterProfile
    tiles: list[TileRecord]
    validation: ValidationReport


class TileIngestionPipeline:
    """Ingest a raster source, validate it, compute tiles, and write the catalog.

    Expected CRS/resolution assumptions:
        - Sources are processed in native CRS/GSD; no reprojection occurs.
        - Tile overlap defaults to 64 px to support boundary stitching in ML
          inference (see ``docs/pipeline.md``).

    The pipeline supports single-machine execution today. Tile records and the
    pure ``process_tile`` function are designed so Dask/Ray can parallelize
    reads and processing without shared mutable state.
    """

    def __init__(
        self,
        *,
        tile_size: int = 1024,
        overlap: int = 64,
        catalog_path: Path | str | None = None,
    ) -> None:
        """Configure tiling parameters and optional catalog destination."""
        self.grid = TileGrid(tile_size=tile_size, overlap=overlap)
        self.catalog_path = Path(catalog_path) if catalog_path else None
        self.audit_logger = ValidationAuditLogger()

    def run(
        self,
        source_path: Path | str,
        *,
        source_id: str | None = None,
        persist_catalog: bool = True,
    ) -> IngestionResult:
        """Execute ingestion → validation → tiling → catalog persistence.

        Args:
            source_path: GeoTIFF/COG path or Sentinel-2 ``.SAFE`` directory.
            source_id: Optional identifier prefix for tile IDs.
            persist_catalog: When True and ``catalog_path`` is set, write tiles.

        Returns:
            ``IngestionResult`` with profile, tile records, and validation.

        Raises:
            ValueError: When validation fails with error-severity issues.
        """
        profile = open_raster_profile(source_path)
        validation = validate_raster_profile(profile)
        self.audit_logger.log_report(validation)

        if profile.format.value == "sentinel2_safe" and profile.band_uris:
            from terra_pipeline.ingestion.sentinel2 import profile_from_band_file

            band_profiles = [profile_from_band_file(Path(uri)) for uri in profile.band_uris]
            band_report = validate_band_crs_consistency(profile.source_uri, band_profiles)
            validation.issues.extend(band_report.issues)
            self.audit_logger.log_report(band_report)

        if not validation.passed:
            msg = f"Ingestion validation failed for {profile.source_uri}"
            raise ValueError(msg)

        tiles = self.grid.build_tile_records(profile, source_id=source_id)
        reader = StreamingTileReader(profile)

        for tile in tiles:
            tile_report = validate_tile_record(
                tile,
                expected_crs_epsg=profile.crs_epsg,
                expected_resolution_x=profile.resolution_x,
                expected_resolution_y=profile.resolution_y,
            )
            if not reader.verify_tile_readable(tile):
                tile_report.add(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="TILE_UNREADABLE",
                        message=f"Unable to read tile window for {tile.tile_id}.",
                        source_uri=profile.source_uri,
                        tile_id=tile.tile_id,
                    )
                )
            if tile_report.issues:
                self.audit_logger.log_report(tile_report)
            if not tile_report.passed:
                msg = f"Tile validation failed for {tile.tile_id}"
                raise ValueError(msg)

        if persist_catalog and self.catalog_path is not None:
            with TileCatalog(self.catalog_path) as catalog:
                catalog.insert_tiles(tiles)
                for issue in validation.issues:
                    catalog.log_validation_issue(issue)

        return IngestionResult(profile=profile, tiles=tiles, validation=validation)
