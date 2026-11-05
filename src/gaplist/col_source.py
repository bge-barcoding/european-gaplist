"""Get a Catalogue of Life release as a ColDP archive.

Three ways, tried in this order:

1. A zip file the user put in ``data/col/manual/`` by hand. This always
   works, also where ChecklistBank cannot be reached.
2. A copy downloaded in an earlier run (kept in ``data/col/``).
3. A fresh download from ChecklistBank.

Whatever the route, the release's version and DOI are read from the
``metadata.yaml`` inside the archive, so the run record always names the
exact release used.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

from . import paths

API = "https://api.checklistbank.org"
ARCHIVE = "https://download.checklistbank.org/col"
# ChecklistBank aliases for the newest release of each type.
LATEST_ALIAS = {"base": "3LR", "xr": "3LXR"}
USER_AGENT = "european-gaplist (https://github.com/bge-barcoding/european-gaplist)"


class SourceError(Exception):
    """The release could not be obtained. The message says what to do."""


@dataclass
class Release:
    path: Path
    version: str
    doi: str | None
    title: str | None


def col_dir() -> Path:
    path = paths.data_dir() / "col"
    (path / "manual").mkdir(parents=True, exist_ok=True)
    return path


def read_metadata(zip_path: Path) -> dict:
    """Read metadata.yaml from a ColDP archive (empty dict if absent)."""
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if n.rsplit("/", 1)[-1] in ("metadata.yaml", "metadata.yml")]
        if not names:
            return {}
        return yaml.safe_load(archive.read(names[0])) or {}


def describe(zip_path: Path) -> Release:
    meta = read_metadata(zip_path)
    version = str(meta.get("version") or meta.get("issued") or zip_path.stem)
    doi = meta.get("doi")
    return Release(path=zip_path, version=version, doi=str(doi) if doi else None, title=meta.get("title"))


def _manual_file() -> Path | None:
    zips = sorted((col_dir() / "manual").glob("*.zip"))
    if len(zips) > 1:
        raise SourceError(
            "There is more than one zip file in data/col/manual/. Keep only the release you want to use."
        )
    return zips[0] if zips else None


def _download(url: str, target: Path) -> None:
    partial = target.with_suffix(".part")
    with requests.get(url, stream=True, timeout=60, headers={"User-Agent": USER_AGENT}) as response:
        if response.status_code == 404:
            raise FileNotFoundError(url)
        response.raise_for_status()
        if "zip" not in response.headers.get("Content-Type", "zip"):
            raise SourceError(f"ChecklistBank did not return a zip file from {url}. Try again later.")
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    partial.rename(target)


def _latest_dataset(release_type: str) -> dict:
    url = f"{API}/dataset/{LATEST_ALIAS[release_type]}"
    response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.json()


def fetch(col_settings: dict) -> Release:
    """Return the release to use, downloading it if needed."""
    manual = _manual_file()
    if manual:
        return describe(manual)

    release_type = col_settings["release_type"]
    version = str(col_settings["version"])
    folder = col_dir()

    try:
        if version == "latest":
            dataset = _latest_dataset(release_type)
            version = str(dataset.get("issued") or dataset.get("version"))
            key = dataset["key"]
            urls = [f"{API}/dataset/{key}/export.zip?format=ColDP"]
        else:
            urls = []
        target = folder / f"{release_type}_{version}_coldp.zip"
        if target.exists():
            return describe(target)
        if release_type == "base":
            urls.append(f"{ARCHIVE}/monthly/{version}_coldp.zip")
        for url in urls:
            try:
                _download(url, target)
                return describe(target)
            except FileNotFoundError:
                continue
    except requests.RequestException as err:
        raise SourceError(
            "ChecklistBank could not be reached "
            f"({err.__class__.__name__}). Either try again later, or download the ColDP "
            "zip of the release by hand from https://www.catalogueoflife.org/data/download "
            "and put it in data/col/manual/."
        ) from err

    raise SourceError(
        f"No ColDP download was found for the {release_type} release '{version}'. Check the "
        "version in sources.yaml, or download the zip by hand from "
        "https://www.catalogueoflife.org/data/download and put it in data/col/manual/."
    )


def extract_name_usage(release: Release) -> Path:
    """Unpack NameUsage.tsv next to the archive (once) and return its path."""
    target = release.path.with_suffix("") / "NameUsage.tsv"
    if target.exists():
        return target
    with zipfile.ZipFile(release.path) as archive:
        members = [n for n in archive.namelist() if n.rsplit("/", 1)[-1] == "NameUsage.tsv"]
        if not members:
            raise SourceError(
                f"{release.path.name} has no NameUsage.tsv. Make sure it is a ColDP download "
                "of the Catalogue of Life, not a DwC-A or TextTree download."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(members[0]) as source, target.open("wb") as sink:
            while chunk := source.read(1 << 20):
                sink.write(chunk)
    return target
