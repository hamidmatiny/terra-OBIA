"""Generate processing tiles over large raster extents."""

from __future__ import annotations

from dataclasses import dataclass

from terra_core.io.cog import TileWindow


@dataclass(frozen=True)
class TileGrid:
    """Compute non-overlapping pixel windows for tiled OBIA processing.

    Tile boundaries are computed in the raster's native pixel grid. All windows
    assume the source COG CRS and resolution; geographic area per tile varies
    with latitude when using projected CRS in metres.

    Args:
        tile_size: Edge length of each square tile in pixels.
        overlap: Pixel overlap between adjacent tiles (for inference stitching).
    """

    tile_size: int = 512
    overlap: int = 64

    def windows(self, width: int, height: int) -> list[TileWindow]:
        """Generate tile windows covering a raster of the given dimensions.

        Args:
            width: Raster width in pixels.
            height: Raster height in pixels.

        Returns:
            List of ``TileWindow`` instances covering the full extent.
        """
        windows: list[TileWindow] = []
        step = self.tile_size - self.overlap
        for row_off in range(0, height, step):
            for col_off in range(0, width, step):
                win_width = min(self.tile_size, width - col_off)
                win_height = min(self.tile_size, height - row_off)
                if win_width <= 0 or win_height <= 0:
                    continue
                windows.append(
                    TileWindow(
                        col_off=col_off,
                        row_off=row_off,
                        width=win_width,
                        height=win_height,
                    )
                )
        return windows
