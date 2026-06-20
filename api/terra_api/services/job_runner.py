"""Execute OBIA processing jobs for the REST API."""

from __future__ import annotations

import json
import logging
import traceback

import geopandas as gpd
import numpy as np

from terra_api.config import settings
from terra_api.schemas import ExportFileInfo, ExportFormatOption, JobStatus
from terra_api.services.job_store import JobStage, job_store
from terra_api.services.model_registry import resolve_model_path
from terra_core.classification import ClassificationConfig, create_classifier
from terra_core.export import ExportFormat, export_objects
from terra_core.segmentation import (
    MergeContext,
    SegmentationConfig,
    create_segmenter,
    merge_tile_segmentations,
)
from terra_core.segmentation.models import TileSegmentationResult
from terra_pipeline.ingest import TileIngestionPipeline
from terra_pipeline.tiling.streaming import StreamingTileReader

logger = logging.getLogger("terra_api.jobs")


def run_job(job_id: str) -> None:
    """Execute the full ingest → segment → classify → export pipeline.

    Expected CRS/resolution assumptions:
        - Input rasters are processed at native GSD in the source CRS.
        - Exported deliverables preserve the source CRS for GIS workflows.

    Args:
        job_id: Identifier of the queued job in ``job_store``.
    """
    record = job_store.get(job_id)
    if record is None:
        return

    try:
        job_store.update(
            job_id,
            status=JobStatus.RUNNING,
            stage=JobStage.INGEST,
            progress_percent=5,
            progress_detail="Validating and tiling input raster",
        )
        output_dir = settings.job_output_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        job_store.update(job_id, output_dir=str(output_dir.resolve()))

        seg_params = record.segmentation_params
        pipeline = TileIngestionPipeline(
            tile_size=int(seg_params["tile_size"]),
            overlap=int(seg_params["overlap"]),
            catalog_path=output_dir / "tiles.db",
        )
        ingestion = pipeline.run(record.source_uri, source_id=job_id[:8], persist_catalog=True)
        profile = ingestion.profile

        job_store.update(
            job_id,
            stage=JobStage.SEGMENT,
            progress_percent=20,
            progress_detail=f"Segmenting {len(ingestion.tiles)} tiles",
        )

        if seg_params["backend"] == "deep":
            seg_config = SegmentationConfig.deep(
                confidence_threshold=float(seg_params["confidence_threshold"]),
            )
            segmenter = create_segmenter(seg_config, pretrained=False)
        else:
            seg_config = SegmentationConfig.classical(
                n_segments=int(seg_params["n_segments"]),
                compactness=float(seg_params["compactness"]),
            )
            segmenter = create_segmenter(seg_config)

        reader = StreamingTileReader(profile)
        tile_results: list[TileSegmentationResult] = []
        data_by_tile: dict[str, np.ndarray] = {}
        total_tiles = max(len(ingestion.tiles), 1)
        for index, tile in enumerate(ingestion.tiles):
            tile_data = reader.read_tile(tile)
            data_by_tile[tile.tile_id] = tile_data.data
            tile_results.append(
                segmenter.segment_tile(
                    tile_data.data.astype(np.float64),
                    tile_id=tile.tile_id,
                    tile_row=tile.tile_row,
                    tile_col=tile.tile_col,
                    col_off=tile.col_off,
                    row_off=tile.row_off,
                    transform=tile.transform,
                    nodata=tile.nodata,
                )
            )
            percent = 20 + int(40 * (index + 1) / total_tiles)
            job_store.update(
                job_id,
                progress_percent=percent,
                progress_detail=f"Segmented tile {index + 1}/{total_tiles}",
            )

        job_store.update(
            job_id,
            stage=JobStage.MERGE,
            progress_percent=65,
            progress_detail="Merging tile boundaries",
        )
        pixel_area = abs(profile.resolution_x * profile.resolution_y)
        merge_context = MergeContext(
            full_width=profile.width,
            full_height=profile.height,
            overlap=int(seg_params["overlap"]),
            transform=profile.transform,
            crs_wkt=profile.crs_wkt,
            pixel_area_m2=pixel_area,
        )
        merged = merge_tile_segmentations(
            tile_results,
            merge_context,
            data_by_tile,
            band_names=seg_config.band_names,
        )

        job_store.update(
            job_id,
            stage=JobStage.CLASSIFY,
            progress_percent=80,
            progress_detail="Assigning stand attributes",
        )
        model_path = resolve_model_path(record.model_id)
        classifier = create_classifier(
            ClassificationConfig(model_artifact_path=model_path),
        )
        classified = classifier.classify_objects(_ensure_crs(merged.objects, profile.crs_wkt))

        job_store.update(
            job_id,
            stage=JobStage.EXPORT,
            progress_percent=90,
            progress_detail="Writing GIS exports",
        )
        export_formats = [_to_core_format(item) for item in record.export_formats]
        exports = export_objects(
            classified.objects,
            output_dir / "exports",
            base_name="stand_delineation",
            formats=export_formats,
        )
        export_infos = [
            ExportFileInfo(
                format=ExportFormatOption(fmt),
                path=str(path.resolve()),
                crs=classified.objects.crs.to_string() if classified.objects.crs else None,
            )
            for fmt, path in exports.items()
        ]

        summary = {
            "tile_count": len(ingestion.tiles),
            "segmentation_backend": seg_params["backend"],
            "model_id": record.model_id,
            "cover_types": classified.objects["cover_type"].value_counts().to_dict()
            if "cover_type" in classified.objects.columns and not classified.objects.empty
            else {},
        }
        job_store.update(
            job_id,
            status=JobStatus.COMPLETED,
            stage=JobStage.DONE,
            progress_percent=100,
            progress_detail="Job completed successfully",
            exports=export_infos,
            object_count=len(classified.objects),
            summary=summary,
        )
        logger.info(
            json.dumps(
                {
                    "event": "job_completed",
                    "job_id": job_id,
                    "object_count": len(classified.objects),
                },
                sort_keys=True,
            )
        )
    except Exception as exc:
        job_store.update(
            job_id,
            status=JobStatus.FAILED,
            stage=JobStage.DONE,
            progress_detail="Job failed",
            error=str(exc),
        )
        logger.error(
            json.dumps(
                {
                    "event": "job_failed",
                    "job_id": job_id,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                sort_keys=True,
            )
        )


def _ensure_crs(objects: gpd.GeoDataFrame, crs_wkt: str | None) -> gpd.GeoDataFrame:
    """Assign CRS to objects when segmentation omitted it."""
    if objects.crs is not None or crs_wkt is None:
        return objects
    return objects.set_crs(crs_wkt)


def _to_core_format(value: str) -> ExportFormat:
    """Map API export format string to core enum."""
    return ExportFormat(value)
