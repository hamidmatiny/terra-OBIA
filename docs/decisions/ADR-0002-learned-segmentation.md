# ADR-0002: Learned segmentation over classical multiresolution segmentation

- **Status:** Accepted
- **Date:** 2025-06-20
- **Deciders:** Terra OBIA engineering team

## Context

Object-Based Image Analysis traditionally follows a two-step pattern:

1. **Segmentation** — Partition the image into homogeneous objects (segments)
2. **Classification** — Assign thematic labels to segments using spectral,
   geometric, and contextual features

Trimble eCognition, the incumbent tool in forestry and government remote
sensing, implements segmentation primarily through **multiresolution segmentation
(MRS)**. MRS is a bottom-up region-merging algorithm controlled by three
parameters:

- **Scale** — Controls object size (larger scale → larger objects)
- **Shape / compactness** — Balances spectral homogeneity vs. geometric compactness
- **Color** — Weight of spectral vs. shape criteria

Analysts tune these parameters iteratively per scene, biome, and sensor. MRS
works well for interactive, scene-by-scene analysis but presents operational
challenges at Terra OBIA's target scale:

| MRS limitation | Impact at province scale |
|----------------|--------------------------|
| Manual parameter tuning | Not reproducible across thousands of tiles |
| Scale sensitivity | Stand boundaries differ between coniferous and deciduous blocks; one global scale fails |
| Compute profile | Region merging on large tiles is CPU-bound and hard to GPU-accelerate |
| Sensor transfer | Parameters tuned on RGB do not transfer to multispectral or LiDAR-derived stacks |
| Knowledge capture | Expert tuning lives in project files, not in versioned model artifacts |

Forestry customers increasingly expect consistent, auditable outputs across
entire management units—not per-analyst project settings.

## Decision

Terra OBIA will adopt a **learned segmentation approach** (deep learning /
modern ML models) as the primary segmentation strategy, exposed through the
`SegmentationModel` interface in `terra_core`.

Specifically:

1. **Default segmentation** — Convolutional or transformer-based models trained
   on labelled tile datasets (instance or semantic segmentation depending on
   workflow).
2. **Tile-native inference** — Models consume COG windows directly; training
   and inference share the same tile geometry defined by `TileGrid`.
3. **Classical MRS (eCognition-style)** — Not implemented. A **SLIC superpixel
   baseline** (`ClassicalSegmenter`) is implemented for comparison, regression
   testing, and CPU-only environments.
4. **Parameter reproducibility** — Model weights, training data version, and
   inference config are versioned artifacts stored alongside job records.

Classification remains a distinct stage (`ClassificationModel`), operating on
features derived from learned segment boundaries or instance masks.

## Rationale

### Reproducibility and auditability

Government forestry clients require that the same inputs and model version
produce identical outputs. Learned models encode segmentation policy in
versioned weights rather than per-operator scale/shape/color sliders. Job
records can cite `model_id`, `weights_sha256`, and `training_dataset_version`
for audit trails.

### Transfer across sensors and biomes

Models can be fine-tuned on regional training data (e.g. BC vs. Quebec forest
structure) while sharing a common architecture. Multispectral, RGB, and
LiDAR-derived channels are handled as input band configuration—not separate
parameter regimes.

### Scalability

Neural segmentation inference is GPU-friendly and embarrassingly parallel over
tiles. Cloud batch services (AWS Batch, Azure ML, Kubernetes GPU node pools)
map naturally to the tiled COG architecture (ADR-0001).

MRS region merging does not parallelize as cleanly within a single large tile
and lacks GPU acceleration in standard implementations.

### Alignment with industry direction

Commercial and research OBIA pipelines increasingly combine deep segmentation
with object-level classification (e.g. Detectron2 instance segmentation +
gradient boosting classifiers). Building on learned segmentation positions
Terra OBIA to incorporate published architectures and pretrained remote sensing
backbones (Prithvi, SatMAE, etc.) as they mature.

### Trade-offs acknowledged

| Learned segmentation | Multiresolution segmentation |
|---------------------|------------------------------|
| Requires labelled training data | Works without labels (unsupervised merge) |
| Black-box without interpretability tooling | Parameters are human-readable |
| GPU infrastructure for training | CPU-only segmentation possible |
| Strong generalization after sufficient training | Sensitive to per-scene tuning |

For enterprise forestry contracts, labelled reference data (existing stand
polygons, photo-interpreted samples) is typically available or can be procured.
The training-data investment is acceptable given reproducibility and scale
requirements.

## Consequences

### Positive

- Consistent segment boundaries across province-scale mosaics
- Versioned, deployable model artifacts replace fragile project-file tuning
- GPU-accelerated tile inference scales with cloud compute
- Clear separation: segmentation model vs. classification model vs. export

### Negative

- Upfront investment in labelled training datasets per workflow and region
- Model interpretability requires additional tooling (not in v1 scope)
- Initial model quality depends on training coverage; cold-start regions need
  bootstrapping strategies (transfer learning, active learning)

### Follow-up work

**Done (as of 2026-06-21):**

- Baseline architecture selected: FCN-ResNet50 semantic segmentation (`DeepSegmenter`)
- `SegmentationModel.segment_tile()` implemented with PyTorch inference (classical SLIC + deep FCN)
- SLIC classical baseline for benchmarking and CPU-only workflows
- Ownership-weighted `merge_tile_segmentations()` with coverage validation tests
- JSON reproducibility logging per tile run

**Remaining:**

- Forestry fine-tuning on regional labeled tiles (replace COCO-pretrained weights)
- Segment Anything Model (SAM) backend implementing `SegmentationModel`
- ONNX export path for deployment-optimized inference
- Model registry and A/B evaluation protocol for segmentation (classification registry exists)
- Documented comparison benchmarks against eCognition MRS on reference AOIs
- Multiresolution segmentation (true eCognition MRS) as optional regulatory fallback

## References

- Trimble eCognition Developer Reference — multiresolution segmentation
- Benz, U. C. et al. (2004). Multi-resolution, object-oriented fuzzy analysis of remote sensing data for GIS-ready information. *ISPRS Journal of photogrammetry and remote sensing*.
- Recent learned OBIA surveys in *Remote Sensing* and *ISPRS* (2022–2024)
