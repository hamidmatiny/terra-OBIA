"""Convert raw GeoTIFFs to Cloud-Optimized GeoTIFFs (COG).

Ingestion preserves the source CRS and ground sample distance. Reprojection
or resampling, if required, must be performed as an explicit upstream step with
documented target CRS and resolution.
"""

from __future__ import annotations

from pathlib import Path


class CogConverter:
    """Convert a raw GeoTIFF into a valid COG with internal tiling and overviews.

    Expected CRS/resolution assumptions:
        - Input and output share the same CRS and pixel grid unless a separate
          reprojection step is applied.
        - Output block size defaults to 512×512 pixels, suitable for windowed
          reads during tiled processing.

    Args:
        block_size: COG internal tile size in pixels.
    """

    def __init__(self, block_size: int = 512) -> None:
        """Configure COG output block size."""
        self.block_size = block_size

    def convert(self, source: Path | str, destination: Path | str) -> Path:
        """Convert ``source`` to a COG written at ``destination``.

        Args:
            source: Path to the input GeoTIFF.
            destination: Path for the output COG.

        Returns:
            Path to the written COG file.

        Raises:
            NotImplementedError: Placeholder until GDAL/rasterio COG driver lands.
        """
        raise NotImplementedError("COG conversion is not yet implemented.")
