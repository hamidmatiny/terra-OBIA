"""Register a terra-obia-etl trained model into terra-OBIA's models directory.

Creates a symlink (preferred) or copy of an ETL artifact directory under
``TERRA_MODELS_DIR`` so the API model registry and classifiers can load it
without manual file moves.

Expected layout (sibling checkout)::

    Cursor/
      terra-OBIA/
      terra-obia-etl/models/stand_geonb_v1_balanced/

One-command handoff::

    poetry run terra-register-etl-model
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REQUIRED_FILES = (
    "metadata.json",
    "cover_type_model.joblib",
    "canopy_closure_model.joblib",
)

DEFAULT_VARIANT = "stand_geonb_v1_balanced"


def _repo_root() -> Path:
    """Return terra-OBIA repository root."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "core").is_dir():
            return candidate
    return Path.cwd()


def default_etl_model_dir(variant: str = DEFAULT_VARIANT) -> Path:
    """Resolve the default sibling ETL model directory."""
    return (_repo_root().parent / "terra-obia-etl" / "models" / variant).resolve()


def validate_artifact(model_dir: Path) -> dict[str, object]:
    """Validate an ETL/OBIA classifier artifact directory.

    Args:
        model_dir: Directory containing metadata.json and joblib weights.

    Returns:
        Parsed metadata.json contents.

    Raises:
        FileNotFoundError: When the directory or required files are missing.
        ValueError: When metadata.json is invalid.
    """
    if not model_dir.is_dir():
        msg = f"Model directory not found: {model_dir}"
        raise FileNotFoundError(msg)
    missing = [name for name in REQUIRED_FILES if not (model_dir / name).exists()]
    if missing:
        msg = f"Incomplete model artifact at {model_dir}; missing: {', '.join(missing)}"
        raise FileNotFoundError(msg)
    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        msg = f"metadata.json must be an object in {model_dir}"
        raise ValueError(msg)
    for key in ("model_id", "feature_columns", "workflow"):
        if key not in metadata:
            msg = f"metadata.json missing required key '{key}' in {model_dir}"
            raise ValueError(msg)
    return metadata


def register_etl_model(
    source: Path,
    *,
    models_dir: Path | None = None,
    name: str | None = None,
    mode: str = "symlink",
) -> Path:
    """Register an ETL model artifact into terra-OBIA's models tree.

    Args:
        source: Source artifact directory (ETL ``models/<variant>``).
        models_dir: Destination models root (default: ``<repo>/models``).
        name: Destination directory name (default: source directory name).
        mode: ``symlink`` (default) or ``copy``.

    Returns:
        Path to the registered artifact directory under ``models_dir``.
    """
    source = source.resolve()
    metadata = validate_artifact(source)
    root = models_dir or (_repo_root() / "models")
    root.mkdir(parents=True, exist_ok=True)
    dest_name = name or source.name
    dest = (root / dest_name).resolve()

    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    if mode == "symlink":
        dest.symlink_to(source, target_is_directory=True)
    elif mode == "copy":
        shutil.copytree(source, dest)
    else:
        msg = f"Unsupported mode '{mode}'; use 'symlink' or 'copy'"
        raise ValueError(msg)

    validate_artifact(dest)
    print(f"Registered model {metadata['model_id']}")
    print(f"  source: {source}")
    print(f"  target: {dest} ({mode})")
    return dest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register a terra-obia-etl model artifact for terra-OBIA inference.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help=(
            "ETL artifact directory "
            f"(default: sibling ../terra-obia-etl/models/{DEFAULT_VARIANT})"
        ),
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=None,
        help="Destination models root (default: <repo>/models)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Destination directory name under models/ (default: source name)",
    )
    parser.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="symlink",
        help="Register via symlink (default) or full copy",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ETL → OBIA model registration."""
    args = _parse_args(argv)
    source = args.source or default_etl_model_dir()
    try:
        register_etl_model(
            source,
            models_dir=args.models_dir,
            name=args.name,
            mode=args.mode,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
