"""Phase 1: build the Catalogue of Life backbone.

Reads the NameUsage table of a ColDP archive and fills two tables:

- ``taxon``: every accepted taxon in the chosen kingdoms, with its parent,
  nested-set indices (lft/rgt), the seven ranks the web app shows, and
  for species and below the species it belongs to;
- ``synonym``: every synonym of those taxa, pointing to its accepted name.

Rebuilding the backbone starts a new run and clears the results of
earlier runs, because everything after Phase 1 depends on it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from . import col_source, db, paths
from .config import Settings, SettingsError, load_settings

ACCEPTED = ("accepted", "provisionally accepted")
SYNONYMS = ("synonym", "ambiguous synonym", "misapplied")
FIXED_RANKS = ("kingdom", "phylum", "class", "order", "family", "genus", "species")
# NameUsage columns we use; ColDP files may prefix them with "col:".
COLUMNS = {
    "ID": "id",
    "parentID": "parent_id",
    "status": "status",
    "rank": "rank",
    "scientificName": "name",
    "authorship": "authorship",
    "extinct": "extinct",
}
RESULT_TABLES = [t for t in db.TABLES if t != "run"]


@dataclass
class BackboneResult:
    ok: bool
    message: str
    by_class: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __str__(self) -> str:
        return f"[{'OK' if self.ok else 'PROBLEM'}] {self.message}"


def load_name_usage(con: duckdb.DuckDBPyConnection, tsv: Path) -> bool:
    """Load NameUsage.tsv into a scratch table ``col_usage``.

    Returns whether the file has an extinct column.
    """
    header = tsv.open(encoding="utf-8").readline().rstrip("\n\r").split("\t")
    plain = {h: h.split(":", 1)[-1] for h in header}
    missing = [c for c in ("ID", "parentID", "status", "rank", "scientificName") if c not in plain.values()]
    if missing:
        raise col_source.SourceError(
            f"NameUsage.tsv lacks the column(s) {', '.join(missing)}. Is this a ColDP download?"
        )
    select = ", ".join(
        f'"{original}" AS {COLUMNS[name]}' for original, name in plain.items() if name in COLUMNS
    )
    if "extinct" not in plain.values():
        select += ", NULL AS extinct"
    if "authorship" not in plain.values():
        select += ", NULL AS authorship"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE col_usage AS
        SELECT {select}
        FROM read_csv(?, delim='\t', header=true, all_varchar=true, quote='', escape='')
        """,
        [str(tsv)],
    )
    return "extinct" in plain.values()


def _is_true(value: str | None) -> bool:
    return str(value).strip().lower() in ("true", "t", "1", "yes")


def build_tree(con: duckdb.DuckDBPyConnection, kingdoms: list[str], exclude_extinct: bool) -> pd.DataFrame:
    """Walk the accepted taxa from the chosen kingdoms down, depth first."""
    rows = con.execute(
        f"""
        SELECT id, parent_id, lower(rank), name, authorship, extinct
        FROM col_usage WHERE lower(status) IN {ACCEPTED}
        """
    ).fetchall()

    info: dict[str, tuple] = {}
    children: dict[str, list[str]] = defaultdict(list)
    roots: list[str] = []
    for taxon_id, parent_id, rank, name, authorship, extinct in rows:
        info[taxon_id] = (parent_id, rank, name, authorship, _is_true(extinct))
        children[parent_id].append(taxon_id)
        if rank == "kingdom" and name in kingdoms:
            roots.append(taxon_id)

    found = {info[r][2] for r in roots}
    absent = [k for k in kingdoms if k not in found]
    if absent:
        raise SettingsError(
            [f"sources.yaml: kingdom '{k}' does not occur in this Catalogue of Life release." for k in absent]
        )

    out: list[tuple] = []
    counter = 0
    for root in sorted(roots, key=lambda r: info[r][2]):
        # Each stack entry: (taxon id, inherited ranks, inherited species id, entering?)
        stack: list[tuple] = [(root, {}, None, True)]
        open_rows: dict[str, int] = {}
        while stack:
            taxon_id, ranks, species_id, entering = stack.pop()
            if not entering:
                counter += 1
                out[open_rows.pop(taxon_id)][6] = counter
                continue
            parent_id, rank, name, authorship, extinct = info[taxon_id]
            if exclude_extinct and extinct:
                continue  # skip the whole subtree
            ranks = dict(ranks)
            if rank in FIXED_RANKS:
                ranks[rank] = name
            if rank == "species":
                species_id = taxon_id
            counter += 1
            open_rows[taxon_id] = len(out)
            out.append(
                [taxon_id, parent_id, rank, name, authorship, counter, None]
                + [ranks.get(r) for r in FIXED_RANKS]
                + [species_id]
            )
            stack.append((taxon_id, ranks, species_id, False))
            for child in sorted(children.get(taxon_id, []), key=lambda c: info[c][2], reverse=True):
                stack.append((child, ranks, species_id, True))

    columns = ["taxon_id", "parent_id", "rank", "name", "authorship", "lft", "rgt", *FIXED_RANKS, "species_id"]
    return pd.DataFrame(out, columns=columns)


def reset_results(con: duckdb.DuckDBPyConnection) -> None:
    for table in RESULT_TABLES:
        con.execute(f'DELETE FROM "{table}"')


def store(con: duckdb.DuckDBPyConnection, tree: pd.DataFrame) -> None:
    con.register("tree_df", tree)
    con.execute(
        """
        INSERT INTO taxon (taxon_id, parent_id, rank, name, authorship, lft, rgt,
                           kingdom, phylum, class, "order", family, genus, species, species_id)
        SELECT taxon_id, parent_id, rank, name, authorship, lft, rgt,
               kingdom, phylum, class, "order", family, genus, species, species_id
        FROM tree_df
        """
    )
    con.unregister("tree_df")
    con.execute(
        f"""
        INSERT INTO synonym (synonym_id, name, authorship, status, accepted_id)
        SELECT u.id, u.name, u.authorship, lower(u.status), u.parent_id
        FROM col_usage u JOIN taxon t ON t.taxon_id = u.parent_id
        WHERE lower(u.status) IN {SYNONYMS}
        """
    )


def summarise(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, int], pd.DataFrame]:
    counts = dict(
        zip(
            ["species", "infraspecific", "synonyms", "no_family", "no_class"],
            con.execute(
                """
                SELECT
                  (SELECT count(*) FROM taxon WHERE rank = 'species'),
                  (SELECT count(*) FROM taxon WHERE species_id IS NOT NULL AND rank <> 'species'),
                  (SELECT count(*) FROM synonym),
                  (SELECT count(*) FROM taxon WHERE rank = 'species' AND family IS NULL),
                  (SELECT count(*) FROM taxon WHERE rank = 'species' AND class IS NULL)
                """
            ).fetchone(),
        )
    )
    by_class = con.execute(
        """
        SELECT coalesce(phylum, '(no phylum)') AS phylum, coalesce(class, '(no class)') AS class,
               count(*) AS species
        FROM taxon WHERE rank = 'species'
        GROUP BY ALL ORDER BY species DESC
        """
    ).df()
    return counts, by_class


def build_backbone(settings: Settings | None = None, database: Path | None = None) -> BackboneResult:
    """Run Phase 1 from start to finish and describe the outcome in plain words."""
    try:
        settings = settings or load_settings()
        release = col_source.fetch(settings.col)
        tsv = col_source.extract_name_usage(release)
    except (SettingsError, col_source.SourceError) as err:
        return BackboneResult(False, str(err))

    database = database or paths.database_path()
    con = db.connect(database)
    try:
        has_extinct = load_name_usage(con, tsv)
        try:
            tree = build_tree(con, settings.col["kingdoms"], settings.col["exclude_extinct"])
        except SettingsError as err:
            return BackboneResult(False, str(err))
        # All or nothing: an interrupted rebuild leaves the previous backbone intact.
        con.execute("BEGIN TRANSACTION")
        try:
            reset_results(con)
            run_id = db.start_run(con, settings)
            store(con, tree)
            con.execute(
                "UPDATE run SET col_version = ?, col_doi = ? WHERE run_id = ?",
                [release.version, release.doi, run_id],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        counts, by_class = summarise(con)
    finally:
        con.close()

    lines = [
        f"Run {run_id}: Catalogue of Life {settings.col['release_type']} release {release.version}"
        + (f" (doi:{release.doi})" if release.doi else "")
        + ".",
        f"{counts['species']:,} species in {', '.join(settings.col['kingdoms'])}"
        + (", extinct taxa left out." if settings.col["exclude_extinct"] else ", extinct taxa included."),
        f"{counts['infraspecific']:,} subspecies and other infraspecific taxa, counted with their species.",
        f"{counts['synonyms']:,} synonyms, available for name matching in the next step.",
    ]
    if settings.col["exclude_extinct"] and not has_extinct:
        lines.append(
            "Warning: this release file has no extinct flags, so extinct taxa could not be left out. "
            "Use the extended ColDP download to fix this."
        )
    if counts["no_family"] or counts["no_class"]:
        lines.append(
            f"Note: {counts['no_family']:,} species have no family and {counts['no_class']:,} no class "
            "in Catalogue of Life. They are kept, but will show empty cells in the target list."
        )
    report = database.parent / "reports"
    report.mkdir(exist_ok=True)
    report_file = report / f"backbone_run{run_id}.tsv"
    by_class.to_csv(report_file, sep="\t", index=False)
    lines.append(f"Species per class written to data/reports/{report_file.name}.")
    return BackboneResult(True, "\n".join(lines), by_class)
