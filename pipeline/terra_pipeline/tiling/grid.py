"""Generate processing tiles over large raster extents."""

from __future__ import annotations

from dataclasses import dataclass

import rasterio.windows

from terra_pipeline.models import RasterProfile, TileRecord, TileWindowSpec


@dataclass(frozen=True)
class TileGrid:
    """Compute overlapping pixel windows for tiled OBIA processing.

    Tile boundaries are computed in the raster's native pixel grid. All windows
    assume the source CRS and resolution; geographic area per tile varies with
    latitude when using projected CRS in metres.

    Default tile size is 1024×1024 with 64 px overlap to reduce segment boundary
    artifacts during downstream inference stitching.

    Args:
        tile_size: Edge length of each square tile in pixels.
        overlap: Pixel overlap between adjacent tiles (for inference stitching).
    """

    tile_size: int = 1024
    overlap: int = 64

    def __post_init__(self) -> None:
        """Validate grid configuration."""
        if self.tile_size <= 0:
            msg = "tile_size must be positive."
            raise ValueError(msg)
        if self.overlap < 0 or self.overlap >= self.tile_size:
            msg = "overlap must be in [0, tile_size)."
            raise ValueError(msg)

    def window_specs(self, width: int, height: int) -> list[TileWindowSpec]:
        """Generate indexed tile windows covering a raster extent.

        Expected CRS/resolution assumptions:
            - ``width`` and ``height`` are pixel dimensions of the source raster.
            - Edge tiles may be smaller than ``tile_size`` when the extent is
              not an exact multiple of the step size.

        Args:
            width: Raster width in pixels.
            height: Raster height in pixels.

        Returns:
            List of ``TileWindowSpec`` instances with row/column indices.
        """
        if width <= 0 or height <= 0:
            return []

        specs: list[TileWindowSpec] = []
        step = self.tile_size - self.overlap
        tile_row = 0
        for row_off in range(0, height, step):
            tile_col = 0
            for col_off in range(0, width, step):
                win_width = min(self.tile_size, width - col_off)
                win_height = min(self.tile_size, height - row_off)
                if win_width <= 0 or win_height <= 0:
                    continue
                specs.append(
                    TileWindowSpec(
                        tile_row=tile_row,
                        tile_col=tile_col,
                        col_off=col_off,
                        row_off=row_off,
                        width=win_width,
                        height=win_height,
                    )
                )
                tile_col += 1
            tile_row += 1
        return specs

    def build_tile_records(
        self,
        profile: RasterProfile,
        *,
        source_id: str | None = None,
    ) -> list[TileRecord]:
        """Build catalog-ready tile records for a raster profile.

        Expected CRS/resolution assumptions:
            - ``profile.transform`` georeferences the full source in its native
              CRS; per-tile transforms are derived via rasterio window math.

        Args:
            profile: Source raster metadata.
            source_id: Optional stable identifier prefix for tile IDs.

        Returns:
            List of ``TileRecord`` entries with geotransform and bbox populated.
        """
        prefix = source_id or _slugify(profile.source_uri)
        records: list[TileRecord] = []
        for spec in self.window_specs(profile.width, profile.height):
            window = rasterio.windows.Window(
                spec.col_off,
                spec.row_off,
                spec.width,
                spec.height,
            )
            tile_transform = rasterio.windows.transform(window, profile.transform)
            left, bottom, right, top = rasterio.windows.bounds(window, profile.transform)
            tile_id = f"{prefix}_{spec.tile_row}_{spec.tile_col}"
            records.append(
                TileRecord(
                    tile_id=tile_id,
                    source_uri=profile.source_uri,
                    tile_row=spec.tile_row,
                    tile_col=spec.tile_col,
                    col_off=spec.col_off,
                    row_off=spec.row_off,
                    width=spec.width,
                    height=spec.height,
                    transform=tile_transform,
                    crs_epsg=profile.crs_epsg,
                    crs_wkt=profile.crs_wkt,
                    resolution_x=profile.resolution_x,
                    resolution_y=profile.resolution_y,
                    nodata=profile.nodata,
                    band_count=profile.band_count,
                    dtype=profile.dtype,
                    bbox=(left, bottom, right, top),
                    tile_size=self.tile_size,
                    overlap=self.overlap,
                )
            )
        return records


def _slugify(value: str) -> str:
    """Create a filesystem-safe identifier from a source URI."""
    slug = value.rstrip("/").split("/")[-1]
    for char in (".", " ", ":", "\\"):
        slug = slug.replace(char, "_")
    return slug.lower()
