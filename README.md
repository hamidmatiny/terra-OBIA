# Terra OBIA

Professional, scalable Object-Based Image Analysis (OBIA) platform for forestry
stand delineation, wetland classification, and land cover/land use mapping —
built for province-scale geospatial datasets and government/enterprise forestry
customers.

> **Status:** Scaffolding stage. Interfaces, documentation, and CI are in place;
> segmentation, classification, and COG I/O are not yet implemented.

## Repository layout

```
core/       Python engine — geospatial I/O, segmentation, classification
api/        FastAPI REST service
pipeline/   Ingestion, COG conversion, tiling, job orchestration
web/        Dashboard placeholder (future)
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

Optional (for future geospatial development):

- GDAL 3.x (system library; required once COG I/O is implemented)

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
| `terra_pipeline` | `from terra_pipeline.tiling.grid import TileGrid` | Ingestion & orchestration |

## Documentation

- [Architecture overview](./docs/architecture.md)
- [Pipeline module (ingestion & tiling)](./docs/pipeline.md)
- [Segmentation module](./docs/segmentation.md)
- [Classification module (stand delineation)](./docs/classification.md)
- [ADR-0001: COG + tiled processing](./docs/decisions/ADR-0001-cog-tiled-processing.md)
- [ADR-0002: Learned segmentation](./docs/decisions/ADR-0002-learned-segmentation.md)
- [Contributing guide](./CONTRIBUTING.md)

## Contributing

Read [CONTRIBUTING.md](./CONTRIBUTING.md) before opening a pull request. Every
module needs a purpose docstring; every geospatial function must document CRS
and resolution assumptions; every PR must update relevant docs.

## License

License TBD.
