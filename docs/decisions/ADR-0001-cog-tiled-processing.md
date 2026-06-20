# ADR-0001: Cloud-Optimized GeoTIFFs and tiled processing for big-data handling

- **Status:** Accepted
- **Date:** 2025-06-20
- **Deciders:** Terra OBIA engineering team

## Context

Terra OBIA targets government and enterprise forestry customers who work with
province-scale geospatial datasets. Typical inputs include:

- Regional orthomosaic mosaics (10–50 cm GSD) covering thousands of square
  kilometres
- Multi-temporal satellite stacks for change detection and LULC mapping
- LiDAR-derived rasters merged into continuous elevation or intensity surfaces

These datasets are terabytes in aggregate. Desktop OBIA tools such as Trimble
eCognition assume imagery fits in local memory or can be accessed through
proprietary tile caches on a single workstation. That model breaks down when:

1. A single scene exceeds available RAM on commodity cloud instances
2. Multiple analysts or automated jobs need concurrent access to the same mosaic
3. Storage lives on object storage (S3-compatible) rather than local disk
4. Processing must scale horizontally across many workers

We need a raster strategy that supports windowed, parallel reads from day one.

## Decision

Terra OBIA will:

1. **Standardize on Cloud-Optimized GeoTIFF (COG)** as the internal raster format
   after ingestion from raw vendor deliverables.
2. **Process imagery in spatial tiles** computed by `TileGrid`, with configurable
   tile size and overlap, never loading full mosaics into worker memory.
3. **Store COGs on object storage** where possible, relying on HTTP range
   requests for partial reads.
4. **Align tile size with COG internal block size** (default 512×512 pixels) to
   minimize read amplification.

Raw formats (non-COG GeoTIFF, JPEG2000, vendor packages) are converted once
during ingestion via `CogConverter` and not re-read in their original form
during processing.

## Rationale

### COG vs. alternatives

| Format | Partial reads | Cloud-native | Ecosystem support | Verdict |
|--------|---------------|--------------|---------------------|---------|
| COG | Yes (HTTP range) | Yes | Excellent (rasterio, GDAL, GeoTIFF spec) | **Selected** |
| Plain GeoTIFF | Poor (no required tiling) | No | Excellent | Rejected — unpredictable I/O |
| Zarr / Cloud-Optimized Zarr | Yes | Yes | Growing | Deferred — less GIS interchange |
| MBTiles / COG via STAC only | Varies | Yes | Good for catalog, not processing | Complementary, not primary |
| Proprietary tile caches | Yes | Vendor-locked | eCognition-specific | Rejected — no portability |

COG balances cloud-native partial access with universal GIS interoperability.
Analysts can inspect COG outputs directly in QGIS or ArcGIS Pro without a
conversion step.

### Tiling vs. whole-raster processing

Whole-raster loading fails predictably at province scale:

- A 30 000 × 40 000 pixel RGB mosaic at uint16 ≈ 7.2 GB per band in memory
- Multi-band, multi-date stacks multiply footprint
- Segmentation often requires additional feature arrays (NDVI, texture, CHM)

Tiled processing bounds memory to `O(tile_size² × bands)` per worker, enabling
horizontal scaling: N workers process N tiles concurrently with near-linear
throughput gains until I/O saturates.

Overlap between tiles handles boundary artifacts in convolutional segmentation
models; overlap width is a workflow parameter, not a code constant.

## Consequences

### Positive

- Workers run on modest cloud instances (e.g. 8–16 GB RAM) regardless of mosaic
  extent
- Object storage becomes the system of record; no full-file staging required
- Parallelism is natural: each tile is an independent work unit
- Outputs remain standard GeoTIFF/vector formats for customer GIS workflows

### Negative

- Ingestion adds a COG conversion step before first processing run
- Tile boundary stitching requires overlap logic and merge strategies
- Highly irregular AOIs may read sparse windows — mitigated by AOI clipping
  during ingestion (future)

### Follow-up work

- Implement `CogConverter` with GDAL COG driver and validation
- Implement `CogReader.read_window` with rasterio
- Add STAC catalog integration for metadata discovery (future ADR)
- Define merge/stitch policy for segmentation outputs at tile edges

## References

- [Cloud Optimized GeoTIFF specification](https://github.com/cogeotiff/cog-spec)
- [rasterio windowed reading](https://rasterio.readthedocs.io/en/stable/topics/windowed-rw.html)
- GDAL `gdal_translate` COG creation options
