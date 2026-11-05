"""Read and check the settings in the ``config`` folder.

Every problem is reported in plain language, naming the file and what to do,
because the people editing these files are not expected to read tracebacks.
All problems are collected and reported together, so a user can fix them in
one go rather than one run at a time.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import paths

ISO_CODE = re.compile(r"^[A-Z]{2}$")
DATE_OR_LATEST = re.compile(r"^(latest|\d{4}-\d{2}-\d{2})$")
CURATION_COLUMNS = ["source", "original_name", "decision", "target_name", "curator", "date", "note"]
CURATION_DECISIONS = {"accept", "map", "reject"}


class _SettingsLoader(yaml.SafeLoader):
    """YAML reader that only treats true/false as yes-or-no values.

    Standard YAML also reads NO, No, ON, OFF, Y and N as true or false,
    which would silently turn Norway's country code (NO) into "false".
    """


_SettingsLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_SettingsLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


class SettingsError(Exception):
    """One or more settings files contain mistakes."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"Please fix the following in the config folder:\n{lines}")


@dataclass
class Settings:
    europe: list[str]
    col: dict[str, Any]
    bold: dict[str, Any]
    gbif: dict[str, Any]
    evidence: dict[str, Any]
    own_projects: list[str]
    own_institutions: list[str]
    curation: list[dict[str, str]] = field(default_factory=list)
    fingerprint: str = ""

    def summary(self) -> str:
        """A few plain sentences describing what a run will do."""
        own = len(self.own_projects) + len(self.own_institutions)
        return "\n".join(
            [
                f"Europe: {len(self.europe)} countries.",
                f"Catalogue of Life: {self.col['release_type']} release, version {self.col['version']}, "
                f"kingdoms {', '.join(self.col['kingdoms'])}.",
                f"BOLD: snapshot {self.bold['snapshot']}, markers {', '.join(self.bold['markers'])}, "
                f"at least {self.bold['min_length']} bases.",
                f"Evidence: a species needs at least {self.evidence['min_sources']} source(s).",
                f"Own barcodes: {own} project(s) or institution(s) listed"
                + (" (none yet, so every barcode counts as 'other')." if own == 0 else "."),
                f"Curation: {len(self.curation)} decision(s) recorded.",
            ]
        )


def _read_yaml(path: Path, problems: list[str]) -> dict[str, Any]:
    if not path.exists():
        problems.append(f"{path.name} is missing. Restore it from GitHub.")
        return {}
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_SettingsLoader) or {}
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        where = f" near line {mark.line + 1}" if mark else ""
        problems.append(
            f"{path.name} cannot be read{where}. Check that every list item starts with "
            f"'- ' and that indentation uses spaces, not tabs."
        )
        return {}
    if not isinstance(data, dict):
        problems.append(f"{path.name} does not have the expected layout. Compare it with the version on GitHub.")
        return {}
    return data


def _check_europe(data: dict[str, Any], problems: list[str]) -> list[str]:
    codes = data.get("include")
    if not isinstance(codes, list) or not codes:
        problems.append("europe.yaml: the 'include' list is empty or missing. List at least one country code.")
        return []
    clean: list[str] = []
    for code in codes:
        text = str(code).strip()
        if not ISO_CODE.match(text):
            problems.append(
                f"europe.yaml: '{text}' is not a two-letter country code in capitals (for example NL or TR)."
            )
        elif text in clean:
            problems.append(f"europe.yaml: {text} is listed twice. Remove one of the lines.")
        else:
            clean.append(text)
    return clean


def _check_sources(data: dict[str, Any], problems: list[str]) -> tuple[dict, dict, dict, dict]:
    col = data.get("col") or {}
    bold = data.get("bold") or {}
    gbif = data.get("gbif") or {}
    evidence = data.get("evidence") or {}

    if col.get("release_type") not in ("base", "xr"):
        problems.append("sources.yaml: col 'release_type' must be either base or xr.")
    if not DATE_OR_LATEST.match(str(col.get("version", ""))):
        problems.append("sources.yaml: col 'version' must be 'latest' or a date written as YYYY-MM-DD.")
    if not col.get("kingdoms"):
        problems.append("sources.yaml: col 'kingdoms' must list at least one kingdom, for example Animalia.")
    if not isinstance(col.get("exclude_extinct"), bool):
        problems.append("sources.yaml: col 'exclude_extinct' must be true or false.")

    if not DATE_OR_LATEST.match(str(bold.get("snapshot", ""))):
        problems.append("sources.yaml: bold 'snapshot' must be 'latest' or a date written as YYYY-MM-DD.")
    if not bold.get("markers"):
        problems.append("sources.yaml: bold 'markers' must list at least one marker, for example COI-5P.")
    if not isinstance(bold.get("min_length"), int) or bold.get("min_length", 0) < 0:
        problems.append("sources.yaml: bold 'min_length' must be a whole number, for example 500.")

    if not gbif.get("checklist_key"):
        problems.append("sources.yaml: gbif 'checklist_key' is missing. Restore it from GitHub.")

    min_sources = evidence.get("min_sources")
    if not isinstance(min_sources, int) or min_sources < 1:
        problems.append("sources.yaml: evidence 'min_sources' must be a whole number of 1 or more.")

    return col, bold, gbif, evidence


def _check_own(data: dict[str, Any], problems: list[str]) -> tuple[list[str], list[str]]:
    projects = data.get("projects") or []
    institutions = data.get("institutions") or []
    if not isinstance(projects, list) or not isinstance(institutions, list):
        problems.append("own_barcodes.yaml: 'projects' and 'institutions' must be lists (or []).")
        return [], []
    return [str(p).strip() for p in projects], [str(i).strip() for i in institutions]


def _read_curation(path: Path, problems: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        problems.append("curation.tsv is missing. Restore it from GitHub.")
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != CURATION_COLUMNS:
            problems.append(
                "curation.tsv: the first row must be exactly these column names, separated by tabs: "
                + ", ".join(CURATION_COLUMNS)
                + ". If you edited it in a spreadsheet, save it as tab-separated text."
            )
            return []
        rows: list[dict[str, str]] = []
        for number, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items()}
            if not any(row.values()):
                continue
            if row["decision"] not in CURATION_DECISIONS:
                problems.append(
                    f"curation.tsv, row {number}: decision '{row['decision']}' must be accept, map or reject."
                )
            if row["decision"] == "map" and not row["target_name"]:
                problems.append(f"curation.tsv, row {number}: a 'map' decision needs a target_name.")
            if not row["original_name"]:
                problems.append(f"curation.tsv, row {number}: original_name is empty.")
            rows.append(row)
        return rows


def _fingerprint(folder: Path) -> str:
    """A short code that changes whenever any settings file changes."""
    digest = hashlib.sha256()
    for name in ("europe.yaml", "sources.yaml", "own_barcodes.yaml", "curation.tsv"):
        path = folder / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def load_settings(folder: Path | None = None) -> Settings:
    """Read all settings files and check them.

    Raises ``SettingsError`` listing every problem found.
    """
    folder = folder or paths.config_dir()
    problems: list[str] = []

    europe = _check_europe(_read_yaml(folder / "europe.yaml", problems), problems)
    col, bold, gbif, evidence = _check_sources(_read_yaml(folder / "sources.yaml", problems), problems)
    projects, institutions = _check_own(_read_yaml(folder / "own_barcodes.yaml", problems), problems)
    curation = _read_curation(folder / "curation.tsv", problems)

    if problems:
        raise SettingsError(problems)

    return Settings(
        europe=europe,
        col=col,
        bold=bold,
        gbif=gbif,
        evidence=evidence,
        own_projects=projects,
        own_institutions=institutions,
        curation=curation,
        fingerprint=_fingerprint(folder),
    )
