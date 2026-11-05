"""Phase 4: combine the evidence and write the target list.

A backbone species is on the European list when at least ``min_sources``
sources (sources.yaml) support it: the earlier checklist, GBIF and BOLD
specimens from Europe. Each listed species gets one row:

- ``data/output/targetlist_seed.tsv``: exactly the columns the target list
  website loads, in its order;
- ``data/output/gaplist_full.tsv``: the same species with all evidence and
  barcode details, for anyone who wants more than the website shows;
- ``data/output/summary.md``: versions used, counts, and gaps per class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from . import db, paths
from .config import Settings, SettingsError, load_settings

SEED_COLUMNS = [
    "Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species", "SpeciesLocality",
    "SpeciesOccurrenceStatus", "Collected", "Wanted", "OwnBarcodes", "OtherBarcodes",
]
RANK_COLUMNS = {"Kingdom": "kingdom", "Phylum": "phylum", "Class": "class", "Order": "order",
                "Family": "family", "Genus": "genus", "Species": "species"}


@dataclass
class ExportResult:
    ok: bool
    message: str
    by_class: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __str__(self) -> str:
        return f"[{'OK' if self.ok else 'PROBLEM'}] {self.message}"


def build_table(con, settings: Settings) -> pd.DataFrame:
    """One row per European species, with every detail."""
    table = con.execute(
        """
        WITH ev AS (
            SELECT taxon_id,
                   count(*) AS sources,
                   bool_or(source = 'legacy') AS in_legacy,
                   bool_or(source = 'gbif') AS in_gbif,
                   bool_or(source = 'bold') AS in_bold,
                   max(source_detail) FILTER (WHERE source = 'legacy') AS legacy_codes,
                   max(record_count) FILTER (WHERE source = 'gbif') AS gbif_records,
                   max(record_count) FILTER (WHERE source = 'bold') AS bold_european_specimens,
                   bool_or(coalesce(possibly_alien, false)) AS possibly_alien
            FROM evidence GROUP BY taxon_id
        )
        SELECT t.taxon_id, t.kingdom, t.phylum, t.class, t."order", t.family, t.genus, t.species,
               coalesce(t.xr_added, false) AS xr_only, ev.*  EXCLUDE (taxon_id),
               coalesce(b.compliant, 0) AS compliant, coalesce(b.european_compliant, 0) AS european_compliant,
               coalesce(b.own, 0) AS own, coalesce(b.other, 0) AS other, coalesce(b.bins, 0) AS bins,
               coalesce(b.specimens, 0) AS bold_specimens
        FROM ev JOIN taxon t ON t.taxon_id = ev.taxon_id AND t.rank = 'species'
        LEFT JOIN barcode_status b ON b.taxon_id = t.taxon_id
        WHERE ev.sources >= ?
        ORDER BY t.phylum, t.class, t."order", t.family, t.species
        """,
        [settings.evidence["min_sources"]],
    ).df()
    if not settings.target_list["include_xr_only"]:
        table = table[~table.xr_only]
    return table.reset_index(drop=True)


def seed_rows(table: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """The website's columns, filled from the full table."""
    tl = settings.target_list
    seed = pd.DataFrame({column: table[rank].fillna("") for column, rank in RANK_COLUMNS.items()})

    def locality(row) -> str:
        parts = [name for flag, name in ((row.in_gbif, "GBIF"), (row.in_bold, "BOLD")) if flag]
        if row.in_legacy:
            parts.append(row.legacy_codes or "checklist")
        return ";".join(parts)

    seed["SpeciesLocality"] = table.apply(locality, axis=1)
    seed["SpeciesOccurrenceStatus"] = ["gap" if n == 0 else "" for n in table.compliant]
    seed["Collected"] = tl["collected"]
    wanted = pd.Series(tl["wanted"]["default"], index=table.index)
    for group in tl["wanted"].get("priority_groups") or []:
        (rank, name), = group.items()
        wanted[table[rank] == name] = tl["wanted"]["priority"]
    seed["Wanted"] = wanted
    seed["OwnBarcodes"] = table.own.astype(int)
    seed["OtherBarcodes"] = table.other.astype(int)
    return seed[SEED_COLUMNS]


def check_seed(seed: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (problems that stop the export, notes that do not)."""
    problems, notes = [], []
    if list(seed.columns) != SEED_COLUMNS:
        problems.append("The columns are not in the order the website expects.")
    if (seed.Species == "").any():
        problems.append(f"{int((seed.Species == '').sum())} rows have no species name.")
    for column in ("Collected", "Wanted", "OwnBarcodes", "OtherBarcodes"):
        if not pd.api.types.is_integer_dtype(seed[column]) or (seed[column] < 0).any():
            problems.append(f"Column {column} must hold whole numbers of 0 or more.")
    for column in SEED_COLUMNS:
        if seed[column].astype(str).str.contains("[\t\n\r]").any():
            problems.append(f"Column {column} contains tabs or line breaks.")
    for column in ("Phylum", "Class", "Order", "Family", "Genus"):
        empty = int((seed[column] == "").sum())
        if empty:
            notes.append(f"{empty:,} species have no {column.lower()} in Catalogue of Life; that cell is left empty.")
    duplicated = seed.Species[seed.Species.duplicated()].nunique()
    if duplicated:
        notes.append(
            f"{duplicated:,} species names occur more than once (homonyms in different groups); each has its own row."
        )
    return problems, notes


def summary_markdown(con, table: pd.DataFrame, by_class: pd.DataFrame, notes: list[str]) -> str:
    run = con.execute(
        "SELECT run_id, col_release_type, col_version, col_doi, legacy_commit, gbif_download_doi, bold_snapshot "
        "FROM run ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    run_id, release_type, col_version, col_doi, legacy, gbif_doi, bold_snapshot = run
    gaps = int((table.compliant == 0).sum())
    lines = [
        f"# European gap list, run {run_id} ({date.today().isoformat()})",
        "",
        "## Sources",
        "",
        f"- Catalogue of Life {release_type} release {col_version}" + (f", https://doi.org/{col_doi}" if col_doi else ""),
        f"- Earlier European checklist: gaplist-data at commit {legacy or 'not used'}",
        "- GBIF occurrence download: " + (f"https://doi.org/{gbif_doi}" if gbif_doi else "not used"),
        f"- BOLD public data package: {bold_snapshot or 'not used'}",
        "",
        "## Totals",
        "",
        f"- European species: {len(table):,}",
        f"- With at least one barcode-compliant sequence: {len(table) - gaps:,} ({(len(table) - gaps) / max(len(table), 1):.1%})",
        f"- Gaps (no compliant barcode): {gaps:,}",
        f"- Species only in the Catalogue of Life eXtended Release: {int(table.xr_only.sum()):,}",
        f"- Possibly alien (GBIF records marked as introduced): {int(table.possibly_alien.sum()):,}",
        "",
        "## Notes",
        "",
        *([f"- {n}" for n in notes] or ["- None."]),
        "",
        "## Per class",
        "",
        "| Phylum | Class | Species | Barcoded | Gaps | Barcoded (%) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
        *[
            f"| {r.phylum} | {r['class']} | {r.species:,} | {r.barcoded:,} | {r.gaps:,} | {r.percent:.1f} |"
            for _, r in by_class.iterrows()
        ],
    ]
    return "\n".join(lines) + "\n"


def export(settings: Settings | None = None, database: Path | None = None) -> ExportResult:
    """Run Phase 4 and describe the outcome in plain words."""
    try:
        settings = settings or load_settings()
    except SettingsError as err:
        return ExportResult(False, str(err))
    database = database or paths.database_path()
    con = db.connect(database)
    try:
        if not con.execute("SELECT count(*) FROM evidence").fetchone()[0]:
            return ExportResult(False, "There is no evidence yet. Run the sections of step 2 first.")
        table = build_table(con, settings)
        seed = seed_rows(table, settings)
        problems, notes = check_seed(seed)
        if problems:
            return ExportResult(False, "The target list was not written, because:\n- " + "\n- ".join(problems))
        missing = [
            name for name, n in (("BOLD barcodes", con.execute("SELECT count(*) FROM barcode_status").fetchone()[0]),
                                 ("GBIF records", int(table.in_gbif.fillna(False).sum())))
            if not n
        ]
        if missing:
            notes.append(f"Not used in this run: {' and '.join(missing)}. Run the corresponding sections to include them.")
        by_class = (
            table.assign(phylum=table.phylum.fillna("(none)"), **{"class": table["class"].fillna("(none)")})
            .groupby(["phylum", "class"])
            .agg(species=("taxon_id", "size"), barcoded=("compliant", lambda s: int((s > 0).sum())))
            .reset_index()
        )
        by_class["gaps"] = by_class.species - by_class.barcoded
        by_class["percent"] = 100 * by_class.barcoded / by_class.species
        by_class = by_class.sort_values("species", ascending=False).reset_index(drop=True)
        out = database.parent / "output"
        out.mkdir(exist_ok=True)
        seed.to_csv(out / "targetlist_seed.tsv", sep="\t", index=False)
        table.to_csv(out / "gaplist_full.tsv", sep="\t", index=False)
        (out / "summary.md").write_text(summary_markdown(con, table, by_class, notes), encoding="utf-8")
    finally:
        con.close()

    gaps = int((seed.SpeciesOccurrenceStatus == "gap").sum())
    lines = [
        f"{len(seed):,} European species on the target list; {gaps:,} of them are gaps "
        f"(no barcode-compliant sequence in BOLD).",
        "Written to data/output/: targetlist_seed.tsv (for the website), gaplist_full.tsv (all details) "
        "and summary.md (sources, totals, per class).",
        *notes,
    ]
    return ExportResult(True, "\n".join(lines), by_class)
