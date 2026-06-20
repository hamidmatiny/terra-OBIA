"""Cloud-Optimized GeoTIFF (COG) reading utilities.

All readers in this module assume input rasters are valid COGs with internal
tiling and overviews. Windowed reads operate in the raster's native CRS; callers
are responsible for reprojection if a target CRS is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TileWindow:
    """A geographic window for tiled raster processing.

    Attributes:
        col_off: Column offset in pixels from the raster origin.
        row_off: Row offset in pixels from the raster origin.
        width: Window width in pixels.
        height: Window height in pixels.
    """

    col_off: int
    row_off: int
    width: int
    height: int


class CogReader:
    """Read windows from Cloud-Optimized GeoTIFFs without loading full rasters.

    Expected CRS/resolution assumptions:
        - The source file is a valid COG readable by rasterio.
        - Pixel size and CRS are taken from the dataset metadata (``crs``,
          ``transform``, ``res`` properties) and are not modified by this reader.
        - Window coordinates are expressed in pixel space of the source raster.

    Args:
        path: Filesystem path to the COG.
    """

    def __init__(self, path: Path | str) -> None:
        """Initialize the reader for the COG at ``path``."""
        self.path = Path(path)

    def metadata(self) -> dict[str, Any]:
        """Return raster metadata without reading pixel data.

        Returns:
            A dictionary with ``crs``, ``width``, ``height``, ``count``,
            ``dtype``, and ``bounds`` keys. Values reflect the source COG as
            stored on disk.
        """
        raise NotImplementedError("COG metadata reading is not yet implemented.")

    def read_window(self, window: TileWindow) -> Any:
        """Read a single pixel window from the COG.

        Args:
            window: Pixel-space window to read.

        Returns:
            A numpy array with shape ``(bands, height, width)`` in the source
            CRS and native resolution.

        Raises:
            NotImplementedError: Placeholder until rasterio integration lands.
        """
        raise NotImplementedError("COG window reading is not yet implemented.")
