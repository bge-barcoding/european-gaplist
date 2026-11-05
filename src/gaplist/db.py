"""The run database (DuckDB)."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import duckdb

from . import __version__, paths
from .config import Settings

TABLES = [
    "run",
    "taxon",
    "synonym",
    "name_resolution",
    "evidence",
    "marker",
    "specimen",
    "barcode",
]


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the database, creating it and its tables if needed."""
    con = duckdb.connect(str(path or paths.database_path()))
    con.execute(files("gaplist").joinpath("schema.sql").read_text(encoding="utf-8"))
    return con


def start_run(con: duckdb.DuckDBPyConnection, settings: Settings) -> int:
    """Record the start of a run and return its number."""
    run_id = con.execute("SELECT coalesce(max(run_id), 0) + 1 FROM run").fetchone()[0]
    con.execute(
        """
        INSERT INTO run (run_id, package_version, settings_fingerprint, col_release_type)
        VALUES (?, ?, ?, ?)
        """,
        [run_id, __version__, settings.fingerprint, settings.col["release_type"]],
    )
    return run_id


def table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in TABLES}
