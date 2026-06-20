"""Lazy windowed reading of raster tiles without full-raster loads."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

import numpy as np
import rasterio
import rioxarray  # noqa: F401  # registers rio accessor for xarray
import xarray as xr
from rasterio.windows import Window

from terra_pipeline.models import RasterFormat, RasterProfile, TileData, TileRecord

if TYPE_CHECKING:
    from collections.abc import Generator


class StreamingTileReader:
    """Stream individual tiles from large rasters using windowed reads.

    Expected CRS/resolution assumptions:
        - Reads occur in the source native CRS and GSD; no reprojection is
          performed.
        - For Sentinel-2 SAFE products, each band JP2 is read for the same
          pixel window and stacked along a band dimension.

    The reader opens datasets lazily and closes them when iteration completes or
    the context manager exits. Only one tile window is materialized in memory
    at a time.
    """

    def __init__(self, profile: RasterProfile) -> None:
        """Configure the reader for a validated raster profile."""
        self.profile = profile

    @contextmanager
    def _open_geotiff(self) -> Generator[rasterio.DatasetReader, None, None]:
        """Open a single GeoTIFF/COG dataset."""
        with rasterio.open(self.profile.band_uris[0]) as dataset:
            yield dataset

    def read_tile(self, tile: TileRecord) -> TileData:
        """Read one tile window into memory.

        Args:
            tile: Catalog tile record describing the pixel window.

        Returns:
            ``TileData`` with a ``(bands, height, width)`` numpy array.

        Raises:
            rasterio.errors.RasterioIOError: When the source is unreadable.
        """
        window = Window(tile.col_off, tile.row_off, tile.width, tile.height)

        if self.profile.format == RasterFormat.SENTINEL2_SAFE:
            arrays = []
            for band_uri in self.profile.band_uris:
                with rasterio.open(band_uri) as dataset:
                    arrays.append(dataset.read(1, window=window))
            data: np.ndarray = np.stack(arrays, axis=0)
        else:
            with rasterio.open(self.profile.band_uris[0]) as dataset:
                data = dataset.read(window=window)

        return TileData(
            tile_id=tile.tile_id,
            data=data,
            transform=tile.transform,
            crs_epsg=tile.crs_epsg,
            crs_wkt=tile.crs_wkt,
            nodata=tile.nodata,
        )

    def read_tile_xarray(self, tile: TileRecord, *, chunked: bool = True) -> xr.DataArray:
        """Read one tile as an ``xarray.DataArray`` via rioxarray.

        Expected CRS/resolution assumptions:
            - The returned DataArray carries CRS metadata from the tile record.
            - When ``chunked=True``, dask chunks are set to the tile shape so
              downstream schedulers can extend this pattern.

        Args:
            tile: Catalog tile record describing the pixel window.
            chunked: When True, apply dask chunks matching the tile extent.

        Returns:
            Lazy or eager ``xarray.DataArray`` for the tile window.
        """
        tile_data = self.read_tile(tile)
        data_array = xr.DataArray(
            tile_data.data,
            dims=("band", "y", "x"),
            coords={
                "band": np.arange(1, tile_data.data.shape[0] + 1),
            },
            attrs={"nodata": tile_data.nodata},
        )
        if tile.crs_wkt:
            data_array = data_array.rio.write_crs(tile.crs_wkt)
        data_array = data_array.rio.write_transform(tile.transform)
        if chunked:
            _, height, width = tile_data.data.shape
            data_array = data_array.chunk({"band": -1, "y": height, "x": width})
        return cast(xr.DataArray, data_array)

    def iter_tiles(self, tiles: list[TileRecord]) -> Iterator[TileData]:
        """Lazily yield tile payloads one at a time.

        Args:
            tiles: Ordered list of catalog tile records.

        Yields:
            ``TileData`` for each tile without retaining prior tiles in memory.
        """
        for tile in tiles:
            yield self.read_tile(tile)

    def verify_tile_readable(self, tile: TileRecord) -> bool:
        """Attempt a minimal read to detect corrupt or mismatched tiles.

        Args:
            tile: Tile to probe.

        Returns:
            True when a 1×1 pixel window can be read successfully.
        """
        window = Window(tile.col_off, tile.row_off, 1, 1)
        try:
            if self.profile.format == RasterFormat.SENTINEL2_SAFE:
                with rasterio.open(self.profile.band_uris[0]) as dataset:
                    dataset.read(1, window=window)
            else:
                with rasterio.open(self.profile.band_uris[0]) as dataset:
                    dataset.read(1, window=window)
        except rasterio.errors.RasterioError:
            return False
        return True
