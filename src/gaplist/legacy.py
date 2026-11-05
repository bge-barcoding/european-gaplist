"""Phase 2, first source: the earlier European checklist (gaplist-data).

Reads the two files of the earlier gap list, matches every species name to
the Catalogue of Life backbone, records which CoL species the checklist
supports (with the checklist's own source codes), and writes a review list
for the names that need a person.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests

from . import db, paths, resolve
from .config import Settings, SettingsError, load_settings

SOURCE = "legacy"
FILES = ("Gap_list_all_updated.csv", "all_specs_and_syn.csv")
USER_AGENT = "european-gaplist (https://github.com/bge-barcoding/european-gaplist)"


class LegacyError(Exception):
    pass


@dataclass
class LegacyRecord:
    name: str
    hints: dict[str, str | None]
    codes: set[str] = field(default_factory=set)
    alternatives: tuple[str, ...] = ()


@dataclass
class LegacyResult:
    ok: bool
    message: str
    outcomes: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __str__(self) -> str:
        return f"[{'OK' if self.ok else 'PROBLEM'}] {self.message}"


def _decode(raw: bytes) -> str:
    """The files are UTF-8, except a few lines in Windows encoding."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def fetch(legacy_settings: dict) -> Path:
    """Return the folder holding both legacy files, downloading them if needed."""
    root = paths.data_dir() / "legacy"
    manual = root / "manual"
    manual.mkdir(parents=True, exist_ok=True)
    if all((manual / f).exists() for f in FILES):
        return manual
    folder = root / legacy_settings["commit"]
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = folder / name
        if target.exists():
            continue
        url = (
            f"https://raw.githubusercontent.com/{legacy_settings['repository']}/"
            f"{legacy_settings['commit']}/data/{name}"
        )
        try:
            response = requests.get(url, timeout=120, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
        except requests.RequestException as err:
            raise LegacyError(
                f"Could not download {name} from GitHub ({err.__class__.__name__}). Try again later, or "
                "put Gap_list_all_updated.csv and all_specs_and_syn.csv in data/legacy/manual/."
            ) from err
        target.write_bytes(response.content)
    return folder


def read_records(folder: Path) -> tuple[list[LegacyRecord], Counter]:
    """One record per distinct species name, with merged source codes."""
    synonyms: dict[str, tuple[str, ...]] = {}
    for raw in (folder / FILES[1]).read_bytes().splitlines():
        parts = [p.strip() for p in _decode(raw).split(";") if p.strip()]
        if len(parts) > 1:
            synonyms[parts[0]] = tuple(parts[1:])

    records: dict[str, LegacyRecord] = {}
    code_counts: Counter = Counter()
    lines = (folder / FILES[0]).read_bytes().splitlines()
    for raw in lines[1:]:
        fields = _decode(raw).rstrip("\r").split(";")
        if len(fields) < 10 or not any(f.strip() for f in fields[1:5]):
            continue  # header rows for higher taxa carry no classification
        name = " ".join(fields[0].split())
        if not name:
            continue
        codes = {c.strip() for c in fields[5].split(",") if c.strip()}
        code_counts.update(codes or {"(none)"})
        record = records.get(name)
        if record is None:
            hints = {"phylum": fields[1], "class": fields[2], "order": fields[3], "family": fields[4]}
            record = records[name] = LegacyRecord(
                name, {k: v.strip() or None for k, v in hints.items()}, alternatives=synonyms.get(name, ())
            )
        record.codes |= codes
    return list(records.values()), code_counts


def store_evidence(con, results: pd.DataFrame, records: list[LegacyRecord]) -> int:
    codes = {r.name: r.codes for r in records}
    resolved = results[results.outcome.isin(resolve.RESOLVED)]
    rows: dict[str, tuple[set, int]] = {}
    for name, taxon_id in zip(resolved.original_name, resolved.taxon_id):
        merged, count = rows.get(taxon_id, (set(), 0))
        rows[taxon_id] = (merged | codes[name], count + 1)
    frame = pd.DataFrame(
        [(t, SOURCE, ",".join(sorted(c)), n) for t, (c, n) in rows.items()],
        columns=["taxon_id", "source", "source_detail", "record_count"],
    )
    con.execute("DELETE FROM evidence WHERE source = ?", [SOURCE])
    con.register("evidence_df", frame)
    con.execute(
        "INSERT INTO evidence (taxon_id, source, source_detail, record_count) "
        "SELECT taxon_id, source, source_detail, record_count FROM evidence_df"
    )
    con.unregister("evidence_df")
    return len(frame)


def write_review(con, results: pd.DataFrame, records: list[LegacyRecord], target: Path) -> int:
    """A spreadsheet of names needing a person, laid out to copy into curation.tsv."""
    todo = results[results.outcome.isin(["review", "unmatched"])].copy()
    hints = {r.name: r.hints for r in records}
    names = dict(con.execute("SELECT taxon_id, name FROM taxon WHERE rank = 'species'").fetchall())
    todo["suggestion"] = todo.candidates.map(lambda c: names.get(c[0], "") if len(c) else "")
    todo["other_candidates"] = todo.candidates.map(lambda c: "; ".join(names.get(x, x) for x in c[1:]))
    for rank in ("family", "order"):
        todo[f"{rank}_in_source"] = todo.original_name.map(lambda n, r=rank: hints[n][r] or "")
    todo["decision"] = ""
    todo["target_name"] = ""
    todo["curator"] = ""
    todo["date"] = ""
    columns = ["source", "original_name", "decision", "target_name", "curator", "date", "outcome",
               "suggestion", "other_candidates", "family_in_source", "order_in_source", "note"]
    todo = todo.sort_values(["outcome", "order_in_source", "family_in_source", "original_name"])[columns]
    explanation = pd.DataFrame(
        {
            "How to use this list": [
                "Each row is a name from the earlier checklist that could not be matched automatically.",
                "outcome 'review': there is a likely match (see 'suggestion') or several possible ones.",
                "outcome 'unmatched': no Catalogue of Life name was found, not even a similar one.",
                "To decide, fill in 'decision': accept (take the suggestion), map (use the name you",
                "type in 'target_name') or reject (leave the name out). Add your initials and the date.",
                "Then copy the first six columns of the rows you decided into config/curation.tsv",
                "and run the notebook section again. Your decisions are kept for all later runs.",
            ]
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        explanation.to_excel(writer, sheet_name="Read me", index=False)
        todo.to_excel(writer, sheet_name="Names to review", index=False)
    return len(todo)


def import_legacy(settings: Settings | None = None, database: Path | None = None) -> LegacyResult:
    """Run the legacy checklist step and describe the outcome in plain words."""
    try:
        settings = settings or load_settings()
        folder = fetch(settings.legacy)
    except (SettingsError, LegacyError) as err:
        return LegacyResult(False, str(err))

    database = database or paths.database_path()
    con = db.connect(database)
    try:
        if not con.execute("SELECT count(*) FROM taxon").fetchone()[0]:
            return LegacyResult(False, "There is no backbone yet. Run section 1 first.")
        records, code_counts = read_records(folder)
        queries = [resolve.Query(SOURCE, r.name, r.hints, r.alternatives) for r in records]
        results = resolve.resolve(con, queries, settings.curation)
        con.execute("BEGIN TRANSACTION")
        try:
            resolve.store(con, results)
            species = store_evidence(con, results, records)
            con.execute(
                "UPDATE run SET legacy_commit = ? WHERE run_id = (SELECT max(run_id) FROM run)",
                [settings.legacy["commit"]],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        review_file = database.parent / "review" / "legacy_names.xlsx"
        to_review = write_review(con, results, records, review_file)
    finally:
        con.close()

    outcomes = results.outcome.value_counts().rename_axis("outcome").reset_index(name="names")
    total = len(results)
    resolved = int(results.outcome.isin(resolve.RESOLVED).sum())
    codes_file = database.parent / "reports" / "legacy_source_codes.tsv"
    codes_file.parent.mkdir(exist_ok=True)
    pd.DataFrame(code_counts.most_common(), columns=["code", "names"]).to_csv(codes_file, sep="\t", index=False)
    lines = [
        f"{total:,} distinct species names read from the earlier checklist.",
        f"{resolved:,} ({resolved / total:.1%}) matched to Catalogue of Life, supporting {species:,} species.",
        f"{to_review:,} names need a person: see data/review/{review_file.name}.",
        "Outcomes: " + ", ".join(f"{o} {n:,}" for o, n in zip(outcomes.outcome, outcomes.names)) + ".",
        f"Source codes used in the checklist are listed in data/reports/{codes_file.name}.",
    ]
    return LegacyResult(True, "\n".join(lines), outcomes)
