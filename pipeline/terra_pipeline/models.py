"""Shared data models for pipeline ingestion, tiling, and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from rasterio.transform import Affine


class RasterFormat(str, Enum):
    """Supported raster source formats for pipeline ingestion."""

    COG = "cog"
    GEOTIFF = "geotiff"
    SENTINEL2_SAFE = "sentinel2_safe"


class ValidationSeverity(str, Enum):
    """Severity level for validation findings."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class RasterProfile:
    """Geospatial metadata for a raster source.

    Expected CRS/resolution assumptions:
        - ``crs_epsg`` and ``transform`` describe the native grid of the source.
        - ``resolution_x`` and ``resolution_y`` are absolute pixel sizes in CRS
          units (typically metres for projected forestry datasets).
    """

    source_uri: str
    format: RasterFormat
    crs_epsg: int | None
    crs_wkt: str | None
    width: int
    height: int
    band_count: int
    dtype: str
    transform: Affine
    resolution_x: float
    resolution_y: float
    nodata: float | None
    is_tiled: bool = False
    band_uris: tuple[str, ...] = ()


@dataclass(frozen=True)
class TileWindowSpec:
    """Pixel window for a single processing tile."""

    tile_row: int
    tile_col: int
    col_off: int
    row_off: int
    width: int
    height: int


@dataclass(frozen=True)
class TileRecord:
    """STAC-like tile metadata stored in the catalog.

    Expected CRS/resolution assumptions:
        - ``transform`` is the georeferencing of this tile window in the source
          CRS; pixel data read with this transform is not reprojected.
        - ``resolution_x``/``resolution_y`` match the source raster GSD.
    """

    tile_id: str
    source_uri: str
    tile_row: int
    tile_col: int
    col_off: int
    row_off: int
    width: int
    height: int
    transform: Affine
    crs_epsg: int | None
    crs_wkt: str | None
    resolution_x: float
    resolution_y: float
    nodata: float | None
    band_count: int
    dtype: str
    bbox: tuple[float, float, float, float]
    tile_size: int
    overlap: int

    def to_stac_item(self) -> dict[str, Any]:
        """Serialize the tile record as a STAC Item-like dictionary."""
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [self.bbox[0], self.bbox[1]],
                    [self.bbox[2], self.bbox[1]],
                    [self.bbox[2], self.bbox[3]],
                    [self.bbox[0], self.bbox[3]],
                    [self.bbox[0], self.bbox[1]],
                ]
            ],
        }
        return {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": self.tile_id,
            "geometry": geometry,
            "bbox": list(self.bbox),
            "properties": {
                "source_uri": self.source_uri,
                "tile_row": self.tile_row,
                "tile_col": self.tile_col,
                "col_off": self.col_off,
                "row_off": self.row_off,
                "width": self.width,
                "height": self.height,
                "transform": list(self.transform),
                "crs_epsg": self.crs_epsg,
                "crs_wkt": self.crs_wkt,
                "resolution_x": self.resolution_x,
                "resolution_y": self.resolution_y,
                "nodata": self.nodata,
                "band_count": self.band_count,
                "dtype": self.dtype,
                "tile_size": self.tile_size,
                "overlap": self.overlap,
            },
            "assets": {
                "source": {
                    "href": self.source_uri,
                    "roles": ["data"],
                    "type": "image/tiff",
                }
            },
        }


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation finding for audit logging."""

    severity: ValidationSeverity
    code: str
    message: str
    source_uri: str
    tile_id: str | None = None


@dataclass
class ValidationReport:
    """Aggregated validation outcome for a source or tile set."""

    source_uri: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True when no error-severity issues are present."""
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def add(self, issue: ValidationIssue) -> None:
        """Append a validation issue to the report."""
        self.issues.append(issue)


@dataclass(frozen=True)
class TileData:
    """In-memory payload for a lazily read tile (parallelizable unit of work).

    Expected CRS/resolution assumptions:
        - ``data`` array values are in the source CRS at native GSD.
        - ``transform`` georeferences the tile origin (top-left) in source CRS
          units.
    """

    tile_id: str
    data: Any
    transform: Affine
    crs_epsg: int | None
    crs_wkt: str | None
    nodata: float | None


@dataclass(frozen=True)
class TileProcessingResult:
    """Output of the pure tile-processing function (placeholder for ML stages)."""

    tile_id: str
    status: Literal["ok", "skipped", "failed"]
    message: str
