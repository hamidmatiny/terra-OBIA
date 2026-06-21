# Terra OBIA

Professional, scalable Object-Based Image Analysis (OBIA) platform for forestry
stand delineation, wetland classification, and land cover/land use mapping —
built for province-scale geospatial datasets and government/enterprise forestry
customers.

> **Status:** Core OBIA pipeline is operational for stand delineation development.
> **Implemented:** tiled ingestion (COG/GeoTIFF/Sentinel-2), segmentation (classical +
> deep), classification training/inference, REST API with GIS export, React review
> dashboard, and folder-based ETL with synthetic data generation.
> **Partial / planned:** `terra_core` `CogReader` window I/O (stub — pipeline uses
> rasterio directly), production infra (`infra/`), wetland/LULC product workflows.

## Repository layout

```
core/       Python engine — geospatial I/O, segmentation, classification
api/        FastAPI REST service
pipeline/   Ingestion, COG conversion, tiling, job orchestration
web/        React review dashboard (MapLibre + Tailwind)
infra/      Docker and Terraform placeholders
docs/       Architecture docs and ADRs
tests/      Test suite
```

See [docs/architecture.md](./docs/architecture.md) for design rationale and data
flow.

## Prerequisites

- **Python 3.11 or newer**
- **[Poetry](https://python-poetry.org/docs/#installation)** 1.8+ for dependency management
- **Git**

Optional (for geospatial development):

- GDAL 3.x (system library; required for rasterio/geopandas)

## Development setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd terra-OBIA
```

### 2. Install dependencies with Poetry

```bash
poetry env use python3.11   # or python3.12
poetry install
```

This creates a virtual environment and installs all runtime and dev dependencies
(FastAPI, rasterio, geopandas, pytest, mypy, ruff, etc.).

### 3. Activate the virtual environment

```bash
poetry shell
```

Or prefix commands with `poetry run` (e.g. `poetry run pytest`).

### 4. Configure environment (optional)

```bash
cp .env.example .env
```

Environment variables use the `TERRA_` prefix. See
[api/terra_api/config.py](./api/terra_api/config.py) for available settings.

## Running the API (development)

```bash
poetry run terra-api
```

Or directly with uvicorn:

```bash
poetry run uvicorn terra_api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify the service:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Interactive API docs: http://localhost:8000/docs

## ETL & model training

Generate synthetic development data:

```bash
poetry run terra-generate-synthetic-aoi --name demo_aoi --size 5km
```

Train from a folder of mixed downloads:

```bash
poetry run terra-train-from-folder --input-dir /path/to/folder --aoi-name my_aoi
```

See [docs/etl.md](./docs/etl.md) for schema details, manifest audit trails, and
synthetic data limitations.

## Quality checks

Run the same checks as CI locally:

```bash
# Lint
poetry run ruff check .

# Format check
poetry run ruff format --check .

# Auto-format (when needed)
poetry run ruff format .

# Type check
poetry run mypy core api pipeline

# Tests
poetry run pytest

# Tests with coverage
poetry run pytest --cov=terra_core --cov=terra_api --cov=terra_pipeline
```

## Project packages

| Package | Import | Purpose |
|---------|--------|---------|
| `terra_core` | `from terra_core.io.cog import CogReader` | OBIA engine |
| `terra_api` | `from terra_api.main import create_app` | REST API |
| `terra_pipeline` | `from terra_pipeline.tiling.grid import TileGrid` | Ingestion, tiling & ETL |

## Documentation

- [Architecture overview](./docs/architecture.md)
- [Pipeline module (ingestion & tiling)](./docs/pipeline.md)
- [ETL & training data](./docs/etl.md)
- [Segmentation module](./docs/segmentation.md)
- [API reference & analyst guide](./docs/api.md)
- [Review dashboard](./docs/dashboard.md)
- [ADR-0001: COG + tiled processing](./docs/decisions/ADR-0001-cog-tiled-processing.md)
- [ADR-0002: Learned segmentation](./docs/decisions/ADR-0002-learned-segmentation.md)
- [Contributing guide](./CONTRIBUTING.md)

## Contributing

Read [CONTRIBUTING.md](./CONTRIBUTING.md) before opening a pull request. Every
module needs a purpose docstring; every geospatial function must document CRS
and resolution assumptions; every PR must update relevant docs.

## License

License TBD.
