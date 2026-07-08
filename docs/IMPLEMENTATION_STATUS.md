# Implementation Status

**Canonical source of truth** for what is built vs. planned in terra-OBIA.
Other docs link here instead of restating status claims. Update this file when
adding tests, stubs, or shipping new modules.

**Last verified:** 2026-06-21 — commit `270b489` — `poetry run pytest` (43 passed),
`poetry run mypy core api pipeline`, `cd web && npm test` (9 passed).

## terra-OBIA component matrix

| Component | Status | Evidence |
|-----------|--------|----------|
| `CogReader` (`terra_core.io.cog`) | **Not started** (stub) | `metadata()` / `read_window()` raise `NotImplementedError`; no tests |
| COG I/O via pipeline (`CogConverter`, rasterio) | **Implemented** | `test_open_geotiff_profile`, `test_streaming_reader_lazy_load`, `test_full_job_lifecycle` |
| `ClassicalSegmenter` / SLIC | **Implemented** | `test_classical_segmentation_output_shape`, `test_classical_segmentation_consistency` |
| `DeepSegmenter` / FCN-ResNet50 | **Partial** | `test_deep_segmentation_output_shape`; COCO-pretrained baseline, not forestry-fine-tuned |
| `merge_tile_segmentations` | **Implemented** | `test_merge_no_missing_area_at_boundaries`, `test_merge_preserves_total_labeled_area` |
| Segmentation reproducibility logging | **Implemented** | `test_config_snapshot_logged` |
| `ClassificationModel` / `StandDelineationClassifier` | **Implemented** | `test_stand_classifier_predicts_attributes`, `test_create_classifier_factory` |
| Gradient boosting training / artifacts | **Implemented** | `test_train_and_save_model_artifact`, `test_load_model_round_trip` |
| ETL → OBIA model handoff | **Implemented** | `terra-register-etl-model`; `test_etl_model_handoff.py` uses real `stand_geonb_v1_balanced` |
| Committed trained model weights | **None in terra-OBIA** | Weights live in terra-obia-etl `models/`; register via CLI (symlink/copy) |
| `TileGrid` / ingestion / validation | **Implemented** | `test_pipeline.py` (9), `test_tiling.py` (5) |
| REST API (jobs, models, review, export) | **Implemented** | `test_full_job_lifecycle`, `test_review_corrections_and_exports` |
| Web review dashboard | **Implemented** | `web/src/__tests__/` (9 Vitest tests) |
| ETL (synthetic AOI, folder loader) | **Implemented** | `test_etl_synthetic.py` (4), `test_etl_folder_loader.py` (3) |
| `pipeline.JobRunner` (`orchestration/runner.py`) | **Not started** (stub) | `submit()` raises `NotImplementedError`; API uses `terra_api.services.job_runner` |

### Coverage snapshot (2026-06-21)

```
poetry run pytest --cov=terra_core --cov=terra_api --cov=terra_pipeline
→ 43 passed, 84% total coverage
```

Notable gaps: `terra_core.io.cog` 0%, CLI entry scripts 0% (not invoked in tests).

## Planned work (high level)

- Implement `CogReader` with rasterio window reads (see ADR-0001)
- Forestry fine-tuning for deep segmenter; SAM backend; ONNX export path
- Production `infra/` deployment assets
- Wetland / LULC product workflows beyond stand delineation

## Related documentation

- [Architecture](./architecture.md)
- [Segmentation](./segmentation.md)
- [Classification](./classification.md)
- [API](./api.md)
- [ADR-0002](./decisions/ADR-0002-learned-segmentation.md)
