# Terra OBIA Review Dashboard

React + Tailwind review UI for forestry analysts. See [docs/dashboard.md](../docs/dashboard.md) for architecture and correction-logging details.

## Quick start

```bash
# From repo root — start API
poetry run terra-api

# Dashboard
cd web
npm install
npm run dev
```

Open http://localhost:5173.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server (port 5173, proxies API) |
| `npm run build` | Production build |
| `npm test` | Vitest component tests |
| `npm run preview` | Preview production build |

## Configuration

Create `web/.env` when API key auth is enabled:

```
VITE_API_KEY=your-terra-api-key
```

## Features

- MapLibre map with stand polygons colored by cover type and confidence
- Segment inspection and manual classification override (logged for retraining)
- Job submission and live progress monitoring via Stage 4 API
- GeoJSON / GeoPackage / Shapefile export downloads
- Analyst approval workflow
