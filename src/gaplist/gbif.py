"""Phase 2, second source: GBIF occurrences in Europe.

Asks GBIF for two species-list downloads, both labelled with Catalogue of
Life eXtended Release keys:

- **main**: animal species with at least one qualifying record in a European
  country (filters in config/sources.yaml);
- **alien**: the same, restricted to records marked as introduced, used only
  to flag species as possibly alien.

GBIF prepares downloads in the background, which can take from minutes to
hours. The download keys are remembered in data/gbif/requests.json, so
running the step again picks up the same downloads instead of asking anew.
Each download has a DOI, which must be cited when the results are used.

Most GBIF species keys are the same as in our backbone. GBIF may run a
slightly older CoL release, so keys that do not join are matched by name.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from . import db, paths, resolve
from .config import Settings, SettingsError, load_settings
from .progress import say

API = "https://api.gbif.org/v1"
SOURCE = "gbif"
USER_AGENT = "european-gaplist (https://github.com/bge-barcoding/european-gaplist)"
DONE = "SUCCEEDED"
FAILED = {"FAILED", "KILLED", "CANCELLED", "FILE_ERASED"}


class GbifError(Exception):
    pass


@dataclass
class GbifResult:
    ok: bool
    message: str
    pending: bool = False
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __str__(self) -> str:
        status = "WAITING" if self.pending else ("OK" if self.ok else "PROBLEM")
        return f"[{status}] {self.message}"


class Client:
    """The few GBIF API calls we need. Tests replace this with a fake."""

    def __init__(self, user: str, password: str):
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers["User-Agent"] = USER_AGENT

    def submit(self, request: dict) -> str:
        response = self.session.post(f"{API}/occurrence/download/request", json=request, timeout=60)
        if response.status_code == 401:
            raise GbifError("GBIF did not accept the user name and password in the .env file.")
        if response.status_code >= 400:
            raise GbifError(f"GBIF refused the download request: {response.text[:300]}")
        return response.text.strip()

    def status(self, key: str) -> dict:
        response = self.session.get(f"{API}/occurrence/download/{key}", timeout=60)
        response.raise_for_status()
        return response.json()

    def download(self, url: str, target: Path) -> None:
        with self.session.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            partial = target.with_suffix(".part")
            with partial.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    handle.write(chunk)
        partial.rename(target)


def credentials() -> tuple[str, str, str]:
    load_dotenv(paths.repo_root() / ".env")
    user, password, email = (os.getenv(k, "").strip() for k in ("GBIF_USER", "GBIF_PASSWORD", "GBIF_EMAIL"))
    if not (user and password and email):
        raise GbifError(
            "A GBIF account is needed to request downloads. Copy .env.example to .env (in the main "
            "folder of the repository) and fill in GBIF_USER, GBIF_PASSWORD and GBIF_EMAIL. You can "
            "register for free at https://www.gbif.org."
        )
    return user, password, email


def build_predicate(settings: Settings, kingdom_keys: list[str], alien_only: bool = False) -> dict:
    g = settings.gbif
    checklist = g["checklist_key"]
    predicates: list[dict] = [
        {"type": "in", "key": "COUNTRY", "values": settings.europe},
        {"type": "in", "key": "TAXON_KEY", "values": kingdom_keys, "checklistKey": checklist},
        {"type": "equals", "key": "OCCURRENCE_STATUS", "value": g["occurrence_status"]},
        {"type": "in", "key": "BASIS_OF_RECORD", "values": g["basis_of_record"]},
    ]
    if g.get("require_coordinates"):
        predicates.append({"type": "equals", "key": "HAS_COORDINATE", "value": "true"})
    excluded = g.get("exclude_degree_of_establishment") or []
    if excluded:
        # Most records have no degree of establishment at all; they must be kept.
        predicates.append(
            {
                "type": "or",
                "predicates": [
                    {"type": "isNull", "parameter": "DEGREE_OF_ESTABLISHMENT"},
                    {"type": "not", "predicate": {"type": "in", "key": "DEGREE_OF_ESTABLISHMENT", "values": excluded}},
                ],
            }
        )
    if alien_only:
        predicates.append({"type": "in", "key": "ESTABLISHMENT_MEANS", "values": g["flag_establishment_means"]})
    return {"type": "and", "predicates": predicates}


def build_request(settings: Settings, kingdom_keys: list[str], alien_only: bool, user: str, email: str) -> dict:
    return {
        "creator": user,
        "notification_address": [email],
        "sendNotification": False,
        "format": "SPECIES_LIST",
        "checklistKey": settings.gbif["checklist_key"],
        "predicate": build_predicate(settings, kingdom_keys, alien_only),
    }


def _fingerprint(request: dict) -> str:
    """Identifies a request by its content, not by who sends it."""
    content = {k: v for k, v in request.items() if k in ("format", "checklistKey", "predicate")}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


def _state_file() -> Path:
    folder = paths.data_dir() / "gbif"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "requests.json"


def _load_state() -> dict:
    path = _state_file()
    return json.loads(path.read_text()) if path.exists() else {}


def _save_state(state: dict) -> None:
    _state_file().write_text(json.dumps(state, indent=2))


def obtain(client: Client, request: dict) -> tuple[str, dict]:
    """Return (download key, status), submitting the request only if it is new."""
    state = _load_state()
    fingerprint = _fingerprint(request)
    key = state.get(fingerprint)
    if key:
        status = client.status(key)
        if status.get("status") not in FAILED:
            return key, status
    key = client.submit(request)
    state[fingerprint] = key
    _save_state(state)
    return key, client.status(key)


def read_species_list(path: Path) -> pd.DataFrame:
    """Read a GBIF species list download: one row per species key."""
    with zipfile.ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.endswith((".csv", ".txt", ".tsv"))]
        if len(members) != 1:
            raise GbifError(f"Unexpected contents in GBIF download {path.name}: {archive.namelist()}")
        raw = archive.read(members[0]).decode("utf-8")
    frame = pd.read_csv(io.StringIO(raw), sep="\t", dtype=str, quoting=3, keep_default_na=False)
    needed = {"speciesKey", "species", "numberOfOccurrences"}
    if not needed <= set(frame.columns):
        raise GbifError(f"GBIF download {path.name} lacks the columns {sorted(needed - set(frame.columns))}.")
    frame = frame[frame.speciesKey.str.strip() != ""].copy()
    frame["numberOfOccurrences"] = pd.to_numeric(frame.numberOfOccurrences, errors="coerce").fillna(0).astype(int)
    hints = [c for c in ("family", "order", "class", "phylum") if c in frame.columns]
    grouped = frame.groupby("speciesKey", as_index=False).agg(
        species=("species", "first"), records=("numberOfOccurrences", "sum"), **{h: (h, "first") for h in hints}
    )
    return grouped


def map_to_backbone(
    con, species: pd.DataFrame, curation: list[dict], review_file: Path | None = None
) -> tuple[dict[str, str], pd.DataFrame, int]:
    """Map GBIF species keys to backbone species: by key, else by name.

    Returns the mapping, the name matching results and how many joined by key.
    """
    con.register("gbif_keys", species[["speciesKey"]])
    joined = {
        k
        for (k,) in con.execute(
            "SELECT g.speciesKey FROM gbif_keys g JOIN taxon t ON t.taxon_id = g.speciesKey AND t.rank = 'species'"
        ).fetchall()
    }
    con.unregister("gbif_keys")
    mapping = {k: k for k in joined}
    rest = species[~species.speciesKey.isin(joined)]
    rest_rows = rest.to_dict("records")  # "class" and "order" are awkward as attribute names
    queries = [
        resolve.Query(SOURCE, row["species"], {h: row.get(h) or None for h in resolve.HINT_RANKS})
        for row in {r["species"]: r for r in rest_rows if r["species"]}.values()
    ]
    results = resolve.resolve(con, queries, curation) if queries else pd.DataFrame()
    if not results.empty:
        by_name = dict(
            zip(results.original_name[results.outcome.isin(resolve.RESOLVED)],
                results.taxon_id[results.outcome.isin(resolve.RESOLVED)])
        )
        for row in rest_rows:
            if row["species"] in by_name:
                mapping[row["speciesKey"]] = by_name[row["species"]]
        if review_file is not None:
            resolve.write_review(
                con, results, {r["species"]: r for r in rest_rows}, review_file, "GBIF",
                {r["species"]: r["records"] for r in rest_rows}, "records",
            )
    return mapping, results, len(joined)


def store_evidence(con, species: pd.DataFrame, mapping: dict[str, str], alien_keys: set[str]) -> pd.DataFrame:
    rows: dict[str, list] = {}
    for row in species.itertuples():
        taxon = mapping.get(row.speciesKey)
        if not taxon:
            continue
        entry = rows.setdefault(taxon, [0, False])
        entry[0] += row.records
        entry[1] = entry[1] or row.speciesKey in alien_keys
    frame = pd.DataFrame(
        [(t, SOURCE, f"{n} records", n, alien) for t, (n, alien) in rows.items()],
        columns=["taxon_id", "source", "source_detail", "record_count", "possibly_alien"],
    )
    con.execute("DELETE FROM evidence WHERE source = ?", [SOURCE])
    con.register("gbif_evidence", frame)
    con.execute(
        "INSERT INTO evidence (taxon_id, source, source_detail, record_count, possibly_alien) "
        "SELECT taxon_id, source, source_detail, record_count, possibly_alien FROM gbif_evidence"
    )
    con.unregister("gbif_evidence")
    return frame


def import_gbif(
    settings: Settings | None = None,
    database: Path | None = None,
    client: Client | None = None,
    wait_minutes: float = 0,
) -> GbifResult:
    """Request (or pick up) the GBIF downloads and record the evidence they give."""
    try:
        settings = settings or load_settings()
        if client is None:
            user, password, email = credentials()
            client = Client(user, password)
        else:
            user, email = "test", "test@example.org"
    except (SettingsError, GbifError) as err:
        return GbifResult(False, str(err))

    database = database or paths.database_path()
    con = db.connect(database)
    try:
        kingdom_keys = [
            k for (k,) in con.execute(
                "SELECT taxon_id FROM taxon WHERE rank = 'kingdom' AND list_contains(?, name)",
                [settings.col["kingdoms"]],
            ).fetchall()
        ]
        if not kingdom_keys:
            return GbifResult(False, "There is no backbone yet. Run section 1 first.")

        downloads = {}
        deadline = time.monotonic() + wait_minutes * 60
        for kind, alien_only in (("main", False), ("alien", True)):
            request = build_request(settings, kingdom_keys, alien_only, user, email)
            say(f"Checking the GBIF {'list of introduced records' if alien_only else 'species list'}...")
            try:
                key, status = obtain(client, request)
                say(f"  download {key}: {str(status.get('status', 'unknown')).lower()}")
                while status.get("status") not in FAILED | {DONE} and time.monotonic() < deadline:
                    time.sleep(30)
                    status = client.status(key)
            except (GbifError, requests.RequestException) as err:
                return GbifResult(False, f"GBIF could not be reached or refused the request: {err}")
            if status.get("status") in FAILED:
                return GbifResult(
                    False,
                    f"GBIF could not prepare download {key} (status {status.get('status')}). "
                    "Run this cell again to ask for a new one.",
                )
            downloads[kind] = (key, status)

        waiting = [k for k, (_, s) in downloads.items() if s.get("status") != DONE]
        if waiting:
            keys = ", ".join(downloads[k][0] for k in waiting)
            return GbifResult(
                False,
                f"GBIF is preparing the download(s) {keys}. This usually takes from a few minutes to a "
                "few hours. Run this cell again later; it will pick up the same downloads.",
                pending=True,
            )

        files = {}
        for kind, (key, status) in downloads.items():
            target = paths.data_dir() / "gbif" / f"{key}.zip"
            if not target.exists():
                say(f"Downloading GBIF list {key}...")
                client.download(status["downloadLink"], target)
            files[kind] = target

        say("Reading the GBIF species lists...")
        main = read_species_list(files["main"])
        alien_keys = set(read_species_list(files["alien"]).speciesKey)
        mapping, resolution, by_key = map_to_backbone(
            con, main, settings.curation, database.parent / "review" / "gbif_names.xlsx"
        )

        con.execute("BEGIN TRANSACTION")
        try:
            if not resolution.empty:
                resolve.store(con, resolution)
            evidence = store_evidence(con, main, mapping, alien_keys)
            main_key, main_status = downloads["main"]
            con.execute(
                "UPDATE run SET gbif_download_key = ?, gbif_download_doi = ?, gbif_alien_download_key = ? "
                "WHERE run_id = (SELECT max(run_id) FROM run)",
                [main_key, main_status.get("doi"), downloads["alien"][0]],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()

    by_name = len(mapping) - by_key
    unplaced = len(main) - len(mapping)
    alien = int(evidence.possibly_alien.sum())
    doi = downloads["main"][1].get("doi")
    lines = [
        f"{len(main):,} animal species with qualifying GBIF records in the configured European countries.",
        f"{by_key:,} matched to the backbone by key, {by_name:,} by name; {unplaced:,} could not be placed"
        + (" (see data/review/gbif_names.xlsx)." if unplaced else "."),
        f"{len(evidence):,} backbone species now have GBIF evidence; {alien:,} of them flagged as possibly alien.",
        f"Please cite the GBIF download: https://doi.org/{doi}" if doi else "GBIF download has no DOI yet.",
    ]
    summary = pd.DataFrame(
        {"step": ["species in GBIF list", "matched by key", "matched by name", "not placed", "possibly alien"],
         "species": [len(main), by_key, by_name, unplaced, alien]}
    )
    return GbifResult(True, "\n".join(lines), summary=summary)
