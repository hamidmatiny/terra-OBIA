# Terra OBIA Review Dashboard

The review dashboard (`/web`) is a React + Tailwind single-page application for forestry analysts to inspect automated stand delineation results, apply manual corrections, approve deliverables, and download GIS exports.

## Purpose

Government forestry customers need to trust automated OBIA output before adopting it operationally. The dashboard provides a familiar map-centric review workflow — similar to desktop GIS tools — with transparent job progress and an explicit audit trail for every manual override.

## Technology stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | React 18 + TypeScript | Type-safe components, broad hiring pool |
| Build | Vite | Fast dev server with API proxy |
| Styling | Tailwind CSS | Consistent, professional UI with minimal CSS |
| Map | MapLibre GL JS | Open-source vector/raster maps, no vendor lock-in |
| Tests | Vitest + React Testing Library | Fast component and hook tests |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  ReviewPage (layout + state orchestration)                      │
├──────────────┬──────────────────────────────┬───────────────────┤
│ JobSubmitForm│ MapViewer (MapLibre GL)      │ SegmentPanel      │
│ JobProgress  │  - OSM basemap               │  - attributes     │
│ ExportBar    │  - GeoJSON segment layers    │  - override form  │
│ Approve btn  │  - click → select segment    │                   │
└──────┬───────┴──────────────┬───────────────┴─────────┬─────────┘
       │                      │                         │
       └──────────────────────┼─────────────────────────┘
                              ▼
                    api/client.ts  →  Terra OBIA REST API (/v1)
                              ▲
                    useJobPolling (2s interval until terminal)
```

### Data flow

1. **Job submission** — Analyst enters a source imagery URI and selects a trained model. `POST /v1/jobs` returns a job ID.
2. **Progress monitoring** — `useJobPolling` polls `GET /v1/jobs/{id}` every 2 seconds until status is `completed` or `failed`. The progress panel shows stage name, percentage, and detail text (e.g. tile counts).
3. **Map display** — When the job completes, `GET /v1/jobs/{id}/features` loads GeoJSON polygons. MapLibre renders fill layers colored by `cover_type` with opacity derived from `confidence`.
4. **Segment review** — Clicking a polygon opens the segment panel with cover type, canopy closure, confidence, and shape metrics (area, perimeter, compactness).
5. **Export** — Download buttons call `GET /v1/jobs/{id}/exports/{format}` for GeoJSON, GeoPackage, or Shapefile (zip).
6. **Approval** — After review, the analyst records approval via `POST /v1/jobs/{id}/approve`.

## Correction logging (training data pipeline)

Manual overrides are first-class training data. When an analyst saves a correction:

1. The dashboard sends `POST /v1/jobs/{id}/corrections` with `object_id`, corrected labels, `analyst_id`, and optional `reason`.
2. The API appends a JSON Lines record to `{job_output_dir}/corrections.jsonl`.
3. The reviewed GeoJSON is written to `{job_output_dir}/review/stand_delineation.geojson` with updated attributes and `manual_override: true`.

### corrections.jsonl schema

Each line is a self-contained audit + training record:

```json
{
  "timestamp": "2026-06-21T14:32:01.123456+00:00",
  "object_id": 42,
  "analyst_id": "jsmith",
  "reason": "Visible hardwood regeneration in orthophoto",
  "original": {
    "cover_type": "conifer",
    "canopy_closure_class": "moderate",
    "confidence": 0.72
  },
  "corrected": {
    "cover_type": "deciduous",
    "canopy_closure_class": "dense"
  }
}
```

### Using corrections for retraining

Corrections accumulate per job and can be aggregated across jobs for periodic model updates:

1. **Collect** — Export `corrections.jsonl` from approved job output directories.
2. **Join** — Match `object_id` to segment feature vectors in the original export (spectral means, shape metrics).
3. **Label** — Use `corrected` values as ground-truth labels; optionally weight by analyst or discard low-confidence originals.
4. **Train** — Append to labeled CSV and run `terra-train-stand-classifier` (see `docs/classification.md`).

This closed loop turns operational review into continuously improving models — a key differentiator for government adoption.

## Running locally

```bash
# Terminal 1 — API
poetry run terra-api

# Terminal 2 — Dashboard
cd web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/v1` and `/health` to the API on port 8000.

Optional: set `VITE_API_KEY` in `web/.env` when the API requires authentication:

```
VITE_API_KEY=your-api-key
```

## Component map

| Component | Responsibility |
|-----------|----------------|
| `ReviewPage` | Page layout, analyst ID persistence, coordinates job → map → panel |
| `JobSubmitForm` | Source URI + model selection, job creation |
| `JobProgressPanel` | Status badge, progress bar, stage labels |
| `MapViewer` | MapLibre map, GeoJSON layers, segment click handling |
| `SegmentPanel` | Attribute display, override form, correction submission |
| `ExportBar` | Download links for completed job exports |
| `useJobPolling` | Polls job status until terminal state |

## Tests

```bash
cd web && npm test
```

Coverage includes segment selection attributes, override form submission, and job status polling behavior.

## Future enhancements

- COG tile endpoint for source imagery overlay (currently OSM basemap + polygons only)
- Batch correction and filter-by-confidence views
- Role-based access tied to government SSO
