"""Phase 3: barcode status from a public BOLD data package (BCDM format).

Reads one BOLD snapshot, keeps records of the configured kingdoms and
markers, matches BOLD species names to the backbone, and records per
species how many barcode-compliant sequences exist: anywhere, from Europe,
"own" (projects or institutions in config/own_barcodes.yaml) and other.

Specimens collected in a European country also count as evidence that a
species occurs in Europe (source "bold").

BOLD data packages need a BOLD login to download, so the snapshot is put in
data/bold/manual/ by hand. TSV, gzipped TSV, Parquet, and zip or tar
archives holding one of these are all accepted.
"""

from __future__ import annotations

import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from . import db, paths, resolve
from .config import Settings, SettingsError, load_settings
from .progress import say

SOURCE = "bold"
DATA_SUFFIXES = (".tsv", ".tsv.gz", ".parquet")
ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz", ".tar")
SPECIES_RANKS = ("species", "subspecies")
COLUMNS = [
    "processid", "sampleid", "inst", "bin_uri", "kingdom", "phylum", "class", "order", "family",
    "species", "identification_rank", "country_iso", "marker_code", "nuc_basecount", "bold_recordset_code_arr",
]
# BOLD snapshot files are named like BOLD_Public.22-May-2026.tsv
SNAPSHOT_DATE = re.compile(r"(\d{1,2}-[A-Za-z]{3}-\d{4})")


class BoldError(Exception):
    pass


@dataclass
class BoldResult:
    ok: bool
    message: str
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __str__(self) -> str:
        return f"[{'OK' if self.ok else 'PROBLEM'}] {self.message}"


def _is_data(name: str) -> bool:
    return name.lower().endswith(DATA_SUFFIXES)


def find_snapshot(snapshot_setting: str) -> tuple[Path, str]:
    """Return the snapshot's data file (unpacking an archive once) and its date."""
    manual = paths.data_dir() / "bold" / "manual"
    manual.mkdir(parents=True, exist_ok=True)
    candidates = [p for p in manual.iterdir() if p.is_file() and (_is_data(p.name) or p.name.lower().endswith(ARCHIVE_SUFFIXES))]
    if not candidates:
        raise BoldError(
            "No BOLD snapshot found. Log in at BOLD, download a data package from "
            "https://v5.boldsystems.org/?p=21708 (TSV or Parquet), and put the file in data/bold/manual/."
        )
    if len(candidates) > 1:
        raise BoldError("There is more than one file in data/bold/manual/. Keep only the snapshot you want to use.")
    source = candidates[0]

    match = SNAPSHOT_DATE.search(source.name)
    date = datetime.strptime(match.group(1), "%d-%b-%Y").date().isoformat() if match else None
    if snapshot_setting != "latest" and date and date != snapshot_setting:
        raise BoldError(
            f"sources.yaml asks for the BOLD snapshot of {snapshot_setting}, but the file in "
            f"data/bold/manual/ is from {date}. Replace the file, or change the date in sources.yaml."
        )
    date = date or (snapshot_setting if snapshot_setting != "latest" else "unknown date")

    if _is_data(source.name):
        return source, date
    unpacked = source.parent.parent / "unpacked" / source.name
    existing = [p for p in unpacked.rglob("*") if p.is_file() and _is_data(p.name)] if unpacked.exists() else []
    if not existing:
        say(f"Unpacking {source.name} (only the first time)...")
        unpacked.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as archive:
                for name in archive.namelist():
                    if _is_data(name):
                        archive.extract(name, unpacked)
        elif tarfile.is_tarfile(source):
            with tarfile.open(source) as archive:
                members = [m for m in archive.getmembers() if m.isfile() and _is_data(m.name)]
                archive.extractall(unpacked, members=members, filter="data")
        existing = [p for p in unpacked.rglob("*") if p.is_file() and _is_data(p.name)]
    if len(existing) != 1:
        raise BoldError(
            f"{source.name} should hold exactly one TSV or Parquet file with the records; found {len(existing)}."
        )
    return existing[0], date


def load_records(con: duckdb.DuckDBPyConnection, path: Path, settings: Settings) -> int:
    """Load the needed columns of the kept records into a scratch table ``bold_raw``."""
    if path.name.lower().endswith(".parquet"):
        reader = f"read_parquet('{path}')"
    else:
        reader = (
            f"read_csv('{path}', delim='\\t', header=true, all_varchar=true, quote='', escape='', "
            "nullstr=['', 'NA', 'None'], ignore_errors=false)"
        )
    available = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {reader}").fetchall()}
    missing = [c for c in COLUMNS if c not in available]
    if missing:
        raise BoldError(f"{path.name} lacks the BCDM column(s) {', '.join(missing)}. Is it a BOLD data package?")
    na = lambda col: f"nullif(nullif(trim(CAST(\"{col}\" AS VARCHAR)), 'NA'), '')"  # noqa: E731
    select = ", ".join(f"{na(c)} AS \"{c}\"" for c in COLUMNS if c != "nuc_basecount")
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE bold_raw AS
        SELECT {select}, TRY_CAST(nullif(CAST(nuc_basecount AS VARCHAR), 'NA') AS INTEGER) AS nuc_basecount
        FROM {reader}
        WHERE list_contains($kingdoms, kingdom) AND list_contains($markers, marker_code)
        """,
        {"kingdoms": settings.col["kingdoms"], "markers": settings.bold["markers"]},
    )
    return con.execute("SELECT count(*) FROM bold_raw").fetchone()[0]


def resolve_names(con: duckdb.DuckDBPyConnection, settings: Settings) -> tuple[pd.DataFrame, dict, dict]:
    """Match the distinct species names used in BOLD to the backbone.

    Returns the results, the classification BOLD gives per name, and the
    number of specimens per name.
    """
    names = con.execute(
        f"""
        SELECT species, first(family) AS family, first("order") AS "order", first(class) AS class,
               first(phylum) AS phylum, count(DISTINCT processid) AS specimens
        FROM bold_raw
        WHERE species IS NOT NULL AND identification_rank IN {SPECIES_RANKS}
        GROUP BY species
        """
    ).fetchall()
    hints = {name: {"family": fam, "order": order, "class": cls, "phylum": phy}
             for name, fam, order, cls, phy, _ in names}
    specimens = {name: n for name, *_, n in names}
    queries = [resolve.Query(SOURCE, name, hints[name]) for name in hints]
    return resolve.resolve(con, queries, settings.curation), hints, specimens


def store(con: duckdb.DuckDBPyConnection, settings: Settings, resolution: pd.DataFrame) -> None:
    resolved = resolution[resolution.outcome.isin(resolve.RESOLVED)][["original_name", "taxon_id"]]
    con.register("bold_names", resolved)
    con.execute("DELETE FROM specimen; DELETE FROM barcode; DELETE FROM barcode_status; DELETE FROM marker;")
    con.execute("INSERT INTO marker SELECT DISTINCT marker_code FROM bold_raw")
    con.execute(
        f"""
        INSERT INTO specimen
        SELECT processid, sampleid, inst, country_iso, species, identification_rank, taxon_id, bin_uri, sets,
               coalesce(list_contains($europe::VARCHAR[], country_iso), false),
               len(list_intersect(sets, $projects::VARCHAR[])) > 0 OR coalesce(list_contains($institutions::VARCHAR[], inst), false)
        FROM (
            SELECT DISTINCT ON (r.processid) r.*, n.taxon_id,
                   CASE WHEN r.bold_recordset_code_arr IS NULL THEN []::VARCHAR[]
                        ELSE list_transform(string_split(r.bold_recordset_code_arr, ','), lambda x: trim(x)) END AS sets
            FROM bold_raw r
            LEFT JOIN bold_names n ON n.original_name = r.species AND r.identification_rank IN {SPECIES_RANKS}
            ORDER BY r.processid
        )
        """,
        {
            "europe": settings.europe,
            "projects": settings.own_projects,
            "institutions": settings.own_institutions,
        },
    )
    con.execute(
        """
        INSERT INTO barcode
        SELECT processid, marker_code, max(nuc_basecount), max(nuc_basecount) >= ?
        FROM bold_raw GROUP BY processid, marker_code
        """,
        [settings.bold["min_length"]],
    )
    con.unregister("bold_names")
    # Counted per species: subspecies identifications count for their species.
    con.execute(
        """
        INSERT INTO barcode_status
        SELECT t.species_id,
               count(DISTINCT s.processid),
               count(*) FILTER (WHERE b.is_compliant),
               count(*) FILTER (WHERE b.is_compliant AND s.is_european),
               count(*) FILTER (WHERE b.is_compliant AND s.is_own),
               count(*) FILTER (WHERE b.is_compliant AND NOT s.is_own),
               count(DISTINCT s.bin_uri) FILTER (WHERE b.is_compliant)
        FROM specimen s
        JOIN taxon t ON t.taxon_id = s.taxon_id
        JOIN barcode b ON b.processid = s.processid
        GROUP BY t.species_id
        """
    )
    con.execute("DELETE FROM evidence WHERE source = ?", [SOURCE])
    con.execute(
        """
        INSERT INTO evidence (taxon_id, source, source_detail, record_count)
        SELECT t.species_id, 'bold', count(*) || ' specimens collected in Europe', count(*)
        FROM specimen s JOIN taxon t ON t.taxon_id = s.taxon_id
        WHERE s.is_european
        GROUP BY t.species_id
        """
    )


def import_bold(settings: Settings | None = None, database: Path | None = None) -> BoldResult:
    """Run Phase 3 and describe the outcome in plain words."""
    try:
        settings = settings or load_settings()
        path, date = find_snapshot(str(settings.bold["snapshot"]))
    except (SettingsError, BoldError) as err:
        return BoldResult(False, str(err))

    database = database or paths.database_path()
    con = db.connect(database)
    try:
        if not con.execute("SELECT count(*) FROM taxon").fetchone()[0]:
            return BoldResult(False, "There is no backbone yet. Run section 1 first.")
        say(f"Reading the BOLD snapshot {path.name} (several minutes for a full snapshot)...")
        try:
            records = load_records(con, path, settings)
        except (BoldError, duckdb.Error) as err:
            return BoldResult(False, f"The BOLD file could not be read: {err}")
        resolution, hints, specimens_per_name = resolve_names(con, settings)
        say("Saving specimens and counting barcodes per species...")
        con.execute("BEGIN TRANSACTION")
        try:
            if not resolution.empty:
                resolve.store(con, resolution)
            store(con, settings, resolution)
            con.execute("UPDATE run SET bold_snapshot = ? WHERE run_id = (SELECT max(run_id) FROM run)", [date])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        review_file = database.parent / "review" / "bold_names.xlsx"
        to_review = (
            resolve.write_review(con, resolution, hints, review_file, "BOLD", specimens_per_name, "specimens")
            if not resolution.empty else 0
        )
        stats = con.execute(
            """
            SELECT
              (SELECT count(*) FROM specimen),
              (SELECT count(*) FROM specimen WHERE taxon_id IS NOT NULL),
              (SELECT count(*) FROM barcode WHERE is_compliant),
              (SELECT count(*) FROM barcode_status WHERE compliant > 0),
              (SELECT count(*) FROM barcode_status WHERE european_compliant > 0),
              (SELECT count(*) FROM evidence WHERE source = 'bold'),
              (SELECT coalesce(sum(own), 0) FROM barcode_status)
            """
        ).fetchone()
    finally:
        con.close()

    specimens, placed, compliant, species_barcoded, species_eu, species_evidence, own = stats
    names = len(resolution)
    names_ok = int(resolution.outcome.isin(resolve.RESOLVED).sum()) if names else 0
    lines = [
        f"BOLD snapshot of {date}: {records:,} {'/'.join(settings.bold['markers'])} records of "
        f"{', '.join(settings.col['kingdoms'])} ({specimens:,} specimens).",
        f"{names:,} species names used in BOLD; {names_ok:,} matched to Catalogue of Life; "
        f"{to_review:,} need a person (see data/review/bold_names.xlsx, the names with most specimens first). "
        f"{placed:,} specimens are placed on a backbone species; the rest are identified only above "
        "species level, or under a name that did not match.",
        f"{compliant:,} sequences are barcode-compliant (at least {settings.bold['min_length']} bases).",
        f"{species_barcoded:,} backbone species have at least one compliant barcode; "
        f"{species_eu:,} have one from a specimen collected in Europe.",
        f"{own:,} compliant barcodes count as 'own'"
        + (" (no projects or institutions listed in own_barcodes.yaml yet)." if not (settings.own_projects or settings.own_institutions) else "."),
        f"{species_evidence:,} species have specimens from Europe, used as evidence that they occur there.",
    ]
    summary = pd.DataFrame(
        {"measure": ["records", "specimens", "placed on a species", "compliant sequences",
                     "species with a barcode", "species with a European barcode"],
         "count": [records, specimens, placed, compliant, species_barcoded, species_eu]}
    )
    return BoldResult(True, "\n".join(lines), summary)
