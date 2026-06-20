"""SQLite catalog storing STAC-like tile metadata records."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rasterio.transform import Affine

from terra_pipeline.models import TileRecord, ValidationIssue, ValidationSeverity


class TileCatalog:
    """Persist and query tile metadata using STAC-like Item records.

    The catalog uses SQLite for lightweight local development and demo
    deployments. The schema mirrors STAC Item fields plus Terra OBIA processing
    properties to support audit trails and future distributed schedulers.
    """

    def __init__(self, db_path: Path | str) -> None:
        """Open or create a catalog database at ``db_path``."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def __enter__(self) -> TileCatalog:
        """Enter context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager and close the connection."""
        self.close()

    def _initialize_schema(self) -> None:
        """Create catalog tables when they do not exist."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tile_items (
                id TEXT PRIMARY KEY,
                stac_version TEXT NOT NULL,
                type TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                tile_row INTEGER NOT NULL,
                tile_col INTEGER NOT NULL,
                geometry TEXT NOT NULL,
                bbox TEXT NOT NULL,
                properties TEXT NOT NULL,
                assets TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS validation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_uri TEXT NOT NULL,
                tile_id TEXT,
                severity TEXT NOT NULL,
                code TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tile_items_source
                ON tile_items(source_uri);
            """
        )
        self._conn.commit()

    def insert_tile(self, tile: TileRecord) -> None:
        """Insert or replace a tile record in the catalog."""
        item = tile.to_stac_item()
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO tile_items (
                id, stac_version, type, source_uri, tile_row, tile_col,
                geometry, bbox, properties, assets, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tile.tile_id,
                item["stac_version"],
                item["type"],
                tile.source_uri,
                tile.tile_row,
                tile.tile_col,
                json.dumps(item["geometry"]),
                json.dumps(item["bbox"]),
                json.dumps(item["properties"]),
                json.dumps(item["assets"]),
                now,
            ),
        )
        self._conn.commit()

    def insert_tiles(self, tiles: list[TileRecord]) -> None:
        """Bulk insert tile records."""
        for tile in tiles:
            self.insert_tile(tile)

    def get_tile(self, tile_id: str) -> TileRecord | None:
        """Fetch a tile record by ID."""
        row = self._conn.execute(
            "SELECT * FROM tile_items WHERE id = ?",
            (tile_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_tile_record(row)

    def list_tiles(self, source_uri: str | None = None) -> list[TileRecord]:
        """List tile records, optionally filtered by source URI."""
        if source_uri is None:
            rows = self._conn.execute(
                "SELECT * FROM tile_items ORDER BY tile_row, tile_col"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tile_items WHERE source_uri = ? ORDER BY tile_row, tile_col",
                (source_uri,),
            ).fetchall()
        return [_row_to_tile_record(row) for row in rows]

    def log_validation_issue(self, issue: ValidationIssue) -> None:
        """Persist a validation issue for audit trails."""
        self._conn.execute(
            """
            INSERT INTO validation_logs (
                source_uri, tile_id, severity, code, message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                issue.source_uri,
                issue.tile_id,
                issue.severity.value,
                issue.code,
                issue.message,
                datetime.now(tz=UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def list_validation_issues(self, source_uri: str) -> list[ValidationIssue]:
        """Return stored validation issues for a source."""
        rows = self._conn.execute(
            """
            SELECT source_uri, tile_id, severity, code, message
            FROM validation_logs
            WHERE source_uri = ?
            ORDER BY id
            """,
            (source_uri,),
        ).fetchall()
        return [
            ValidationIssue(
                severity=ValidationSeverity(row["severity"]),
                code=row["code"],
                message=row["message"],
                source_uri=row["source_uri"],
                tile_id=row["tile_id"],
            )
            for row in rows
        ]


def _row_to_tile_record(row: sqlite3.Row) -> TileRecord:
    """Deserialize a database row into a ``TileRecord``."""
    properties: dict[str, Any] = json.loads(row["properties"])
    transform_values = properties["transform"]
    transform = Affine.from_gdal(*transform_values[:6])
    bbox_values = json.loads(row["bbox"])
    return TileRecord(
        tile_id=row["id"],
        source_uri=row["source_uri"],
        tile_row=row["tile_row"],
        tile_col=row["tile_col"],
        col_off=properties["col_off"],
        row_off=properties["row_off"],
        width=properties["width"],
        height=properties["height"],
        transform=transform,
        crs_epsg=properties.get("crs_epsg"),
        crs_wkt=properties.get("crs_wkt"),
        resolution_x=properties["resolution_x"],
        resolution_y=properties["resolution_y"],
        nodata=properties.get("nodata"),
        band_count=properties["band_count"],
        dtype=properties["dtype"],
        bbox=(bbox_values[0], bbox_values[1], bbox_values[2], bbox_values[3]),
        tile_size=properties["tile_size"],
        overlap=properties["overlap"],
    )
