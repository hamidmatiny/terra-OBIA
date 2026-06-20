# Terra OBIA API

The Terra OBIA REST API exposes province-scale OBIA processing — segmentation,
stand classification, and GIS export — to government and enterprise forestry
workflows. OpenAPI documentation is available at `/docs` when the service is
running.

## Authentication

| Mode | Configuration | Header |
|------|---------------|--------|
| Development | `TERRA_API_KEY` unset | None required |
| Production | `TERRA_API_KEY=your-secret` | `X-API-Key: your-secret` |

**Enterprise upgrade path:** Replace API-key middleware with OAuth2/OpenID
Connect (Azure AD, GC Keycloak) for single sign-on. The current header-based
approach satisfies initial security reviews while SSO is provisioned.

All requests emit structured JSON logs (`request_id`, method, path, status,
latency) for audit and SIEM integration.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/jobs` | Submit a stand delineation job |
| `GET` | `/v1/jobs/{id}` | Poll status and progress |
| `GET` | `/v1/jobs/{id}/results` | Retrieve GIS exports |
| `GET` | `/v1/models` | List trained classification models |
| `GET` | `/health` | Service health check |

---

## Developer reference — full job lifecycle

### 1. List available models

```http
GET /v1/models
X-API-Key: your-secret
```

```json
{
  "models": [
    {
      "model_id": "stand_20250620T120000Z_a1b2c3d4",
      "workflow": "stand_delineation",
      "training_date": "2025-06-20T12:00:00+00:00",
      "training_data_description": "NB DNRED 2025 photo-interpreted stands",
      "overall_accuracy": 0.87,
      "mean_iou": 0.82,
      "artifact_path": "/app/models/stand_v20250620",
      "accuracy_report_path": "/app/models/stand_v20250620/accuracy_report.md"
    }
  ]
}
```

### 2. Submit a job

```http
POST /v1/jobs
Content-Type: application/json
X-API-Key: your-secret
```

```json
{
  "source_uri": "/data/nb_province_mosaic.tif",
  "workflow": "stand_delineation",
  "model_id": "stand_20250620T120000Z_a1b2c3d4",
  "segmentation": {
    "backend": "classical",
    "n_segments": 200,
    "compactness": 12.0,
    "tile_size": 1024,
    "overlap": 64
  },
  "export_formats": ["geojson", "gpkg", "shp"]
}
```

**Response (202 Accepted):**

```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "queued",
  "message": "Job accepted and queued for processing."
}
```

### 3. Poll job status

```http
GET /v1/jobs/f47ac10b-58cc-4372-a567-0e02b2c3d479
```

```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "running",
  "workflow": "stand_delineation",
  "created_at": "2025-06-20T14:00:00Z",
  "updated_at": "2025-06-20T14:05:30Z",
  "progress": {
    "percent": 45,
    "stage": "segment",
    "detail": "Segmented tile 12/28"
  },
  "error": null
}
```

Status values: `queued`, `running`, `completed`, `failed`.

### 4. Retrieve results

```http
GET /v1/jobs/f47ac10b-58cc-4372-a567-0e02b2c3d479/results
```

```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "completed",
  "object_count": 1842,
  "model_id": "stand_20250620T120000Z_a1b2c3d4",
  "segmentation_parameters": {
    "backend": "classical",
    "n_segments": 200,
    "compactness": 12.0,
    "tile_size": 1024,
    "overlap": 64
  },
  "exports": [
    {
      "format": "geojson",
      "path": "/outputs/jobs/f47ac10b.../exports/stand_delineation.geojson",
      "crs": "EPSG:32619"
    },
    {
      "format": "gpkg",
      "path": "/outputs/jobs/f47ac10b.../exports/stand_delineation.gpkg",
      "crs": "EPSG:32619"
    },
    {
      "format": "shp",
      "path": "/outputs/jobs/f47ac10b.../exports/stand_delineation.shp",
      "crs": "EPSG:32619"
    }
  ],
  "summary": {
    "tile_count": 28,
    "segmentation_backend": "classical",
    "cover_types": {"conifer": 920, "deciduous": 612, "mixed": 310}
  }
}
```

Open export files directly in **QGIS** (Layer → Add Layer) or **ArcGIS Pro**
(Add Data). CRS and attributes are preserved.

---

## Getting started — for GIS analysts

This guide is for foresters and GIS staff who will run stand delineation jobs,
not for software developers.

### What Terra OBIA does

Terra OBIA automates **forest stand delineation** — the same work you may
currently do manually in Trimble eCognition. It:

1. Reads your province-scale orthomosaic or satellite mosaic
2. Finds stand-like objects (segmentation)
3. Assigns **cover type**, **canopy closure**, and a **confidence score** to each stand polygon
4. Delivers results as **Shapefile, GeoPackage, or GeoJSON** for QGIS/ArcGIS

### Before you begin

You need:

- A **GeoTIFF or COG** mosaic covering your area of interest (UTM projection recommended)
- An **API key** from your Terra OBIA administrator
- The **model ID** for the stand classifier trained on your region (ask your admin, or call `GET /v1/models`)

### Step-by-step

1. **Start the service** (your IT team handles this) or connect to the hosted URL.

2. **Submit your mosaic** using the job form in Swagger UI (`/docs`) or a tool like Postman:
   - Set `source_uri` to the path of your imagery on the server
   - Choose the `model_id` for your region
   - Leave default export formats to get Shapefile + GeoPackage + GeoJSON

3. **Wait for processing.** Province-scale jobs can take minutes to hours. Check progress:
   - `status: running` with `progress.percent` increasing
   - `stage` shows where the job is: ingest → segment → classify → export

4. **Download results** when `status: completed`. Your IT team maps the `exports[].path` files to a shared drive or download endpoint.

5. **Open in QGIS:**
   - *Layer → Add Layer → Add Vector Layer*
   - Select `stand_delineation.gpkg` (recommended) or `.shp`
   - Verify the layer CRS matches your other forestry layers (e.g. EPSG:32619 for New Brunswick UTM 19N)

6. **Review low-confidence stands.** Filter where `confidence < 0.5` or `needs_review = true` and photo-interpret those polygons manually.

### Understanding confidence scores

| Confidence | Recommended action |
|------------|-------------------|
| 0.8 – 1.0 | Accept in production mapping |
| 0.5 – 0.8 | Spot-check before sign-off |
| Below 0.5 | Manual review required |

Confidence reflects how certain the classifier is — not the overall product accuracy. Ask your administrator for the model's **accuracy report** (`accuracy_report.md`) for validation statistics.

### Attribute fields in GIS exports

| Field | Description |
|-------|-------------|
| `cover_type` | Dominant cover class (conifer, deciduous, mixed, …) |
| `canopy_closure_class` | Canopy closure bin (sparse, moderate, dense, …) |
| `confidence` | Classifier certainty (0–1) |
| `area_m2` | Stand area in square metres |
| `perimeter_m` | Stand perimeter in metres |
| `compactness` | Shape compactness (1.0 = circular) |
| `mean_band_*` | Mean spectral values per input band |

Shapefile exports use shortened column names (10-character DBF limit). Use GeoPackage for full attribute names.

---

## Related documentation

- [Classification module](./classification.md)
- [Segmentation module](./segmentation.md)
- [Pipeline module](./pipeline.md)
- [Architecture overview](./architecture.md)
