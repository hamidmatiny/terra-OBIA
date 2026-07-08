# Contributing to Terra OBIA

Thank you for contributing. Terra OBIA serves government and enterprise forestry
customers who depend on reproducible, well-documented geospatial processing.
Documentation is not optional—it is part of every change.

## Documentation standard

Every contribution must meet the following requirements before merge.

### Module docstrings

Every Python module (every `.py` file) must begin with a module-level docstring
that explains **what the module does** and **where it sits in the system**.

```python
"""Convert raw GeoTIFFs to Cloud-Optimized GeoTIFFs (COG).

Ingestion preserves the source CRS and ground sample distance. Reprojection
or resampling, if required, must be performed as an explicit upstream step.
"""
```

Package `__init__.py` files should summarize the package purpose and list public
exports.

### Geospatial function documentation

Every function or method that reads, writes, transforms, or assumes geospatial
data must document its **CRS** and **resolution** expectations in the docstring.
Use a dedicated paragraph or `Expected CRS/resolution assumptions:` section:

```python
def read_window(self, window: TileWindow) -> np.ndarray:
    """Read a single pixel window from the COG.

    Expected CRS/resolution assumptions:
        - Window coordinates are in pixel space of the source raster.
        - Output arrays use the source CRS and native GSD; no reprojection
          is performed.

    Args:
        window: Pixel-space window to read.

    Returns:
        Array with shape (bands, height, width).
    """
```

Document when functions **do** reproject or resample, including target CRS and
target resolution.

### Architecture Decision Records (ADRs)

Significant design choices (storage format, algorithm family, deployment target,
breaking API changes) require a new ADR in `/docs/decisions/` using the naming
convention `ADR-NNNN-short-title.md`. Increment the number sequentially. ADRs
are immutable once accepted; supersede with a new ADR rather than editing history.

### PR-sized documentation updates

Every pull request must update relevant documentation:

| Change type | Required doc update |
|-------------|---------------------|
| New module or public API | Module docstring + update `docs/architecture.md` if boundaries shift + `docs/IMPLEMENTATION_STATUS.md` |
| New geospatial function | CRS/resolution assumptions in docstring |
| New workflow or data format | ADR or architecture section + `docs/IMPLEMENTATION_STATUS.md` if shipping or stubbing |
| API endpoint change | Route docstring + future OpenAPI notes |
| Configuration / env var | `.env.example` and README |

If a change does not require documentation updates, explain why in the PR
description.

## Development setup

See [README.md](./README.md) for environment setup with Poetry, Python 3.11+,
and running quality checks locally.

## Code quality gates

All changes must pass before merge (enforced by CI):

```bash
poetry run ruff check .
poetry run ruff format --check .
bash scripts/check_doc_status.sh
poetry run mypy core api pipeline
poetry run pytest
```

Fix lint and type errors; do not disable rules without an ADR or issue
discussion.

## Style conventions

- **Formatter/linter:** Ruff (line length 100, Google docstring convention)
- **Typing:** Strict mypy; annotate all public functions
- **Imports:** Absolute imports from package roots (`terra_core`, `terra_api`,
  `terra_pipeline`)
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes

## Testing

- Add tests for new behaviour in `/tests/`
- Prefer unit tests for pure logic (tiling, config parsing)
- Use `httpx`/`TestClient` for API route tests
- Do not commit large geospatial fixtures; use tiny synthetic rasters or mocks

## Commit and PR guidelines

- Write clear commit messages focused on **why**, not just what
- Keep PRs focused; split unrelated changes
- Link related issues or ADRs in the PR description
- Ensure CI is green before requesting review

## Questions

Open a GitHub issue for design questions that may need an ADR before
implementation.
