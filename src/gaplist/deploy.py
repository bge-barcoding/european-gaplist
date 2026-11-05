"""Phase 4, last step: put the target list on the website.

The website (bge-targetlist) reads its data from the Postgres table
"Targetlist". This step replaces the contents of that table with
data/output/targetlist_seed.tsv, in one transaction: if anything goes wrong,
the website keeps the old list. The website shows the new list after its
next cache refresh (every few hours) or a restart.

The database details come from the .env file (TARGETLIST_DB_*). Nothing is
written unless ``confirm=True`` is given; without it, the step only checks
the connection and the table and says what it would do.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

from . import paths
from .export import SEED_COLUMNS

TABLE = "Targetlist"
# Columns the database fills itself (computed or identity) are not written.
WRITTEN = SEED_COLUMNS + ["DateCreated", "DateModified"]


@dataclass
class DeployResult:
    ok: bool
    message: str

    def __str__(self) -> str:
        return f"[{'OK' if self.ok else 'PROBLEM'}] {self.message}"


def connection_settings() -> dict[str, str]:
    load_dotenv(paths.repo_root() / ".env")
    keys = {"host": "TARGETLIST_DB_HOST", "dbname": "TARGETLIST_DB_NAME", "user": "TARGETLIST_DB_USER",
            "password": "TARGETLIST_DB_PASSWORD"}
    values = {k: os.getenv(v, "").strip() for k, v in keys.items()}
    missing = [keys[k] for k, v in values.items() if not v]
    if missing:
        raise ValueError(
            "To update the website, fill in " + ", ".join(missing) + " in the .env file. "
            "Ask the target list administrator for these details."
        )
    port = os.getenv("TARGETLIST_DB_PORT", "").strip()
    if port:
        values["port"] = port
    return values


def deploy(confirm: bool = False, seed_file: Path | None = None, connection: dict | None = None) -> DeployResult:
    seed_file = seed_file or paths.data_dir() / "output" / "targetlist_seed.tsv"
    if not seed_file.exists():
        return DeployResult(False, "There is no target list yet. Run section 4 first.")
    seed = pd.read_csv(seed_file, sep="\t", dtype=str, keep_default_na=False)
    if list(seed.columns) != SEED_COLUMNS:
        return DeployResult(False, f"{seed_file.name} does not have the website's columns. Run section 4 again.")

    try:
        connection = connection or connection_settings()
    except ValueError as err:
        return DeployResult(False, str(err))

    try:
        with psycopg.connect(**connection, connect_timeout=20) as con:
            columns = {
                r[0] for r in con.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = %s", [TABLE]
                ).fetchall()
            }
            if not columns:
                return DeployResult(False, f'The database has no table "{TABLE}". Is this the target list database?')
            absent = [c for c in WRITTEN if c not in columns]
            if absent:
                return DeployResult(
                    False,
                    f'The "{TABLE}" table lacks the column(s) {", ".join(absent)}. The website may have changed; '
                    "nothing was written.",
                )
            current = con.execute(f'SELECT count(*) FROM "{TABLE}"').fetchone()[0]
            if not confirm:
                return DeployResult(
                    True,
                    f"Connection works. The website now lists {current:,} species; this would replace them with "
                    f"{len(seed):,}. Nothing was changed. To go ahead, run deploy(confirm=True).",
                )
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            numbers = {"Collected", "Wanted", "OwnBarcodes", "OtherBarcodes"}
            with con.transaction():
                con.execute(f'DELETE FROM "{TABLE}"')
                names = ", ".join(f'"{c}"' for c in WRITTEN)
                with con.cursor().copy(f'COPY "{TABLE}" ({names}) FROM STDIN') as copy:
                    # Empty text stays an empty string, as the website's own loader does.
                    for record in seed.to_dict("records"):
                        copy.write_row(
                            [int(record[c]) if c in numbers else record[c] for c in SEED_COLUMNS] + [now, now]
                        )
            written = con.execute(f'SELECT count(*) FROM "{TABLE}"').fetchone()[0]
    except psycopg.Error as err:
        return DeployResult(False, f"The database reported a problem, and nothing was changed: {err}")

    return DeployResult(
        True,
        f"The website's table now holds {written:,} species (it held {current:,}). The website shows them "
        "after its next cache refresh or a restart.",
    )
