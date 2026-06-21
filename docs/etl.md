# ETL & Training Data

The `terra_pipeline.etl` package prepares orthoimagery and inventory labels for stand
delineation model training. It supports two workflows:

1. **Synthetic AOI generation** — unblock development without real imagery downloads.
2. **Folder-based loading** — discover, validate, and clean messy government data drops.

Processed outputs always land in:

```
{TERRA_DATA_DIR}/processed/{aoi_name}/
├── orthoimagery.cog.tif      # RGB+NIR COG
├── inventory_labels.gpkg     # FO/WL/NF/WA inventory polygons
├── training_labels.csv       # Per-object features for Stage 3 training
└── manifest.json             # Audit trail
```

Set `TERRA_DATA_DIR` in `.env` (default: `./data`).

---

## Inventory schema (FO / WL / NF / WA)

Label vectors are normalized to a unified inventory schema:

| Code | Meaning | Training use |
|------|---------|----------------|
| **FO** | Forest | Exported to training CSV with `cover_type` (conifer/deciduous/mixed) and `canopy_closure_class` |
| **WL** | Wetland | Retained in inventory GeoPackage; excluded from stand classifier training |
| **NF** | Non-forest / cleared | Retained in inventory; excluded from training |
| **WA** | Water | Retained in inventory; excluded from training |

The folder loader auto-detects class columns by matching common government field names
(`inventory_class`, `INV_CLASS`, `LC_CLASS`, `cover_type`, `canopy_closure_class`, etc.).
Ambiguous schemas are flagged in the manifest for manual confirmation.

---

## Synthetic AOI generator

### Purpose

Generate internally consistent orthoimagery and label polygons for pipeline and
API integration testing when real provincial data is unavailable.

### CLI

```bash
poetry run terra-generate-synthetic-aoi --name demo_aoi --size 5km --resolution 2
```

| Flag | Default | Description |
|------|---------|-------------|
| `--name` | (required) | AOI folder name under `processed/` |
| `--size` | `5km` | Extent (`5km`, `1000`, etc.) |
| `--resolution` | `2` | Ground sample distance (metres) |
| `--seed` | `42` | Random seed |
| `--data-dir` | `TERRA_DATA_DIR` | Output root override |
| `--no-training-csv` | off | Skip training CSV export |

### Generation logic

1. **Land-cover mosaic** — A coarse random field is smoothed and thresholded into
   NF / FO / WL / WA patches. Synthetic drainage sinuses inject connected water (WA)
   features resembling stream networks.
2. **Forest subtypes** — FO cells receive conifer / deciduous / mixed sub-patches.
3. **Spectral painting** — Each class is painted with class-appropriate RGB+NIR
   signatures (forest: high NIR / low red; water: low all bands; wetland: intermediate;
   non-forest: high visible / low NIR) plus Gaussian noise.
4. **Vectorization** — Class regions are polygonized with realistic minimum stand
   sizes; FO polygons inherit dominant subtype and random canopy closure.
5. **ETL pass** — The raw raster and labels run through the same orthoimagery and
   inventory ETL steps as real data, producing a COG and GeoPackage.

### Limitations

> **Synthetic data is for pipeline development only.** Accuracy results from synthetic
> AOIs are not meaningful and **must not be cited** in any sales, evaluation, or
> government reporting material. Synthetic textures approximate spectral separability
> but do not reproduce real sensor noise, terrain shadow, species mixing, or legacy
> inventory errors.

---

## Folder-based data loader

### Purpose

Accept a single directory of mixed downloads (zips, misnamed files, multiple formats)
and produce clean processed outputs plus an audit manifest explaining what worked and
what was skipped.

### CLI

```bash
poetry run terra-train-from-folder \
  --input-dir /path/to/messy_downloads \
  --aoi-name my_aoi \
  --output-dir models/my_aoi
```

This runs: **discover → validate/clean → ETL → train → accuracy report**.

### Supported inputs

| Type | Formats |
|------|---------|
| Raster | GeoTIFF, COG, JPEG2000; Sentinel-2 `.SAFE` folders; content sniffing for misnamed files |
| Vector | Shapefile, GeoPackage, GeoJSON, CSV with WKT or lat/lon columns |
| Archives | `.zip` (extracted recursively before discovery) |

### Auto-detection

Discovery is **not** extension-only:

1. Zip archives are extracted to a scratch area; corrupt zips are logged and skipped.
2. Each file is classified by extension **and** content inspection (rasterio open,
   geopandas read, CSV column sniff).
3. Rasters are validated for CRS and readability; vectors for CRS and class columns.
4. CRS mismatches are reprojected to the project standard (default EPSG:32619).
5. The first usable raster and first usable vector drive ETL; additional files are
   listed as skipped in the manifest.

### Manifest

`manifest.json` records every discovered file with status:

- `usable` — validated and processed (or extracted from zip)
- `skipped` — recognized but not used (duplicate raster, unknown extension, etc.)
- `error` — corrupt or unreadable
- `ambiguous` — usable but schema needs analyst confirmation

This is the audit trail for “why didn't my data work?”

### Worked example

Suppose a government analyst drops these files into `~/Downloads/nb_forest_2024/`:

```
nb_forest_2024/
├── ortho_final.zip          # contains provincial ortho GeoTIFF
├── stand_labels.shp         # forest inventory with DOM_COVER column
├── old_draft.tif            # corrupt partial download
└── notes_readme.txt
```

Run:

```bash
poetry run terra-train-from-folder \
  --input-dir ~/Downloads/nb_forest_2024 \
  --aoi-name nb_forest_2024
```

Expected outcome:

- Zip extracted; ortho converted to COG under `data/processed/nb_forest_2024/`
- Shapefile normalized to FO inventory schema; `DOM_COVER` mapped to `cover_type`
- Corrupt `old_draft.tif` skipped with error in manifest
- `notes_readme.txt` skipped as unknown
- Training CSV built from FO polygons with spectral + shape features
- Model artifact and `accuracy_report.md` printed to console

Inspect `data/processed/nb_forest_2024/manifest.json` for the full audit trail.

---

## Python API

```python
from terra_pipeline.etl import EtlConfig, generate_synthetic_aoi, load_folder

# Synthetic development AOI
result = generate_synthetic_aoi("demo_aoi", size="1km", resolution=5.0)

# Folder discovery + ETL
folder_result = load_folder("/path/to/folder", "my_aoi")
```

---

## Correction data → retraining

Manual corrections logged via the review dashboard (`corrections.jsonl`) can be
appended to labeled training CSVs and fed into `terra-train-stand-classifier`.
See [dashboard.md](./dashboard.md) for the closed-loop retraining workflow.

---

## Related documentation

- [Pipeline module](./pipeline.md) — ingestion and tiling
- [Classification module](./classification.md) — stand delineation training
- [Architecture overview](./architecture.md)
