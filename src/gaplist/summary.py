"""The run report (data/output/summary.md), written for people who have not
seen the pipeline: every number is explained where it appears.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

import pandas as pd

from . import paths
from .config import Settings

# Plain names for the classes most often on the list. Classes not listed here
# are shown with their scientific name only.
COMMON_NAMES = {
    "Insecta": "insects",
    "Arachnida": "spiders, mites, harvestmen and relatives",
    "Gastropoda": "snails and slugs",
    "Bivalvia": "mussels, clams and other bivalves",
    "Cephalopoda": "octopuses, squid and cuttlefish",
    "Malacostraca": "crabs, shrimps, woodlice, amphipods and relatives",
    "Copepoda": "copepods",
    "Ostracoda": "seed shrimps",
    "Branchiopoda": "water fleas and fairy shrimps",
    "Collembola": "springtails",
    "Diplopoda": "millipedes",
    "Chilopoda": "centipedes",
    "Pycnogonida": "sea spiders",
    "Teleostei": "bony fishes",
    "Elasmobranchii": "sharks and rays",
    "Aves": "birds",
    "Mammalia": "mammals",
    "Reptilia": "reptiles",
    "Amphibia": "amphibians",
    "Ascidiacea": "sea squirts",
    "Chromadorea": "roundworms (nematodes)",
    "Enoplea": "roundworms (nematodes)",
    "Polychaeta": "bristle worms",
    "Clitellata": "earthworms and leeches",
    "Trematoda": "flukes",
    "Cestoda": "tapeworms",
    "Monogenea": "monogenean flatworms",
    "Demospongiae": "sponges",
    "Hydrozoa": "hydroids and relatives",
    "Anthozoa": "corals and sea anemones",
    "Scyphozoa": "jellyfish",
    "Eurotatoria": "rotifers",
    "Gymnolaemata": "moss animals (bryozoans)",
    "Echinoidea": "sea urchins",
    "Asteroidea": "starfish",
    "Ophiuroidea": "brittle stars",
    "Holothuroidea": "sea cucumbers",
}

# Plain names for the orders most often among species only in the eXtended Release.
ORDER_NAMES = {
    "Coleoptera": "beetles", "Lepidoptera": "butterflies and moths", "Diptera": "flies and midges",
    "Hymenoptera": "wasps, bees and ants", "Hemiptera": "true bugs", "Orthoptera": "grasshoppers and crickets",
    "Odonata": "dragonflies and damselflies", "Trichoptera": "caddisflies", "Araneae": "spiders",
    "Trombidiformes": "mites", "Sarcoptiformes": "mites", "Mesostigmata": "mites", "Ixodida": "ticks",
    "Opiliones": "harvestmen", "Stylommatophora": "land snails and slugs", "Amphipoda": "amphipods",
    "Isopoda": "woodlice and other isopods", "Collembola": "springtails",
}
NUMBER_WORDS = {1: "one", 2: "two", 3: "all three"}

SOURCE_LABELS = {
    (True, True, True): "all three sources",
    (True, True, False): "the previous checklist and GBIF",
    (True, False, True): "the previous checklist and BOLD",
    (False, True, True): "GBIF and BOLD",
    (True, False, False): "only the previous checklist",
    (False, True, False): "only GBIF",
    (False, False, True): "only BOLD",
}


def _n(value) -> str:
    return f"{int(value):,}"


def _pct(part, whole) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "0%"


def _flags(table: pd.DataFrame) -> pd.DataFrame:
    return table[["in_legacy", "in_gbif", "in_bold"]].fillna(False).astype(bool)


def _evidence_table(table: pd.DataFrame) -> list[str]:
    flags = _flags(table)
    counts = flags.value_counts()
    rows = ["| Says the species occurs in Europe | Species | Share of the list |", "| --- | ---: | ---: |"]
    for key, label in SOURCE_LABELS.items():
        n = int(counts.get(key, 0))
        rows.append(f"| {label} | {_n(n)} | {_pct(n, len(table))} |")
    return rows


def _plain(text: str) -> str:
    """Sort key ignoring accents, so that Åland sorts with the As."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _country_names(codes: list[str]) -> list[str]:
    """Country names from the comments in config/europe.yaml; the code where there is none."""
    names: dict[str, str] = {}
    path = paths.config_dir() / "europe.yaml"
    if path.exists():
        for match in re.finditer(r"^\s*-\s*([A-Z]{2})\s*#\s*([^(\n]+)", path.read_text(encoding="utf-8"), re.M):
            names[match.group(1)] = match.group(2).strip()
    return [names.get(code, code) for code in codes]


def _largest_orders(subset: pd.DataFrame, n: int = 3) -> str:
    counts = subset["order"].dropna().value_counts().head(n)
    parts = [
        f"{order}{' (' + ORDER_NAMES[order] + ')' if order in ORDER_NAMES else ''}: {_n(count)}"
        for order, count in counts.items()
    ]
    return "; ".join(parts)


def _review_counts(con) -> dict[str, int]:
    rows = con.execute(
        "SELECT source, count(*) FROM name_resolution WHERE outcome IN ('review', 'unmatched') GROUP BY source"
    ).fetchall()
    return dict(rows)


def build(con, table: pd.DataFrame, by_class: pd.DataFrame, notes: list[str], settings: Settings) -> str:
    run_id, release_type, col_version, col_doi, legacy, gbif_doi, bold_snapshot, fingerprint = con.execute(
        "SELECT run_id, col_release_type, col_version, col_doi, legacy_commit, gbif_download_doi, bold_snapshot, "
        "settings_fingerprint FROM run ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    total = len(table)
    barcoded = int((table.compliant > 0).sum())
    gaps = total - barcoded
    barcoded_eu = int((table.european_compliant > 0).sum())
    flags = _flags(table)
    single = int((flags.sum(axis=1) == 1).sum())
    gbif_only = int((flags.in_gbif & ~flags.in_legacy & ~flags.in_bold).sum())
    xr = table[table.xr_only]
    xr_flags = _flags(xr)
    xr_gbif_only = int((xr_flags.in_gbif & ~xr_flags.in_legacy & ~xr_flags.in_bold).sum())
    alien = int(table.possibly_alien.fillna(False).sum())
    own_total, other_total = int(table.own.sum()), int(table.other.sum())
    own_species = int((table.own > 0).sum())
    review = _review_counts(con)
    min_length = settings.bold["min_length"]
    markers = ", ".join(settings.bold["markers"])
    min_sources = settings.evidence["min_sources"]
    bold_used = bool(bold_snapshot)
    gbif_used = bool(flags.in_gbif.any())

    lines = [
        "# The European DNA barcode gap list",
        "",
        f"*Run {run_id}, report written on {date.today().isoformat()}.*",
        "",
        "This report summarises one run of the European gap list pipeline. It says which European animal "
        "species already have a public DNA barcode and which do not yet (the \"gaps\"), where that information "
        "comes from, and how much confidence the numbers deserve. It is meant to be read on its own: you do not "
        "need to know how the pipeline works. Words in *italics* are explained in the glossary at the end.",
        "",
    ]

    if not (bold_used and gbif_used):
        missing = [name for used, name in ((gbif_used, "GBIF"), (bold_used, "BOLD")) if not used]
        lines += [
            f"> **Incomplete run.** {' and '.join(missing)} data were not used in this run. "
            + ("Without BOLD, no barcodes are counted, so every species shows as a gap. " if not bold_used else "")
            + "Treat the numbers below as provisional.",
            "",
        ]

    lines += [
        "## In short",
        "",
        f"- **{_n(total)} animal species** count as occurring in Europe.",
        f"- **{_n(barcoded)} of them ({_pct(barcoded, total)}) have at least one public DNA barcode** of the "
        f"agreed quality (a *barcode-compliant* sequence).",
        f"- **{_n(gaps)} ({_pct(gaps, total)}) are gaps**: no public barcode-compliant sequence exists for them yet.",
        f"- Of the barcoded species, {_n(barcoded_eu)} ({_pct(barcoded_eu, barcoded)}) have a barcode from a "
        f"specimen collected in Europe. The other {_n(barcoded - barcoded_eu)} are covered only by specimens "
        "collected elsewhere, which may not reflect the genetic variation within Europe.",
        "",
        "## How a species gets on the list",
        "",
        ("A species is on the list when " + (
            "at least one of three independent sources says" if min_sources == 1
            else f"at least {NUMBER_WORDS.get(min_sources, min_sources)} of three independent sources say"
            if min_sources == 2 else "all three independent sources say"
        ) + " it occurs in Europe. \"Europe\" here is a political area of "
         f"{len(settings.europe)} countries and territories, chosen by the project: "
         + ", ".join(sorted(_country_names(settings.europe), key=_plain)) + "."),
        "",
        "1. **The previous European checklist**, compiled by hand for the earlier gap list from national "
        "checklists, Fauna Europaea and other sources.",
        "2. **GBIF**, the Global Biodiversity Information Facility: at least one record of the species in one of "
        "these countries, with map coordinates, not from captivity or cultivation, and not a fossil.",
        "3. **BOLD**, the Barcode of Life Data System: at least one specimen of the species collected in one of "
        "these countries.",
        "",
        "Every species name from every source is first matched to one shared list of names, the "
        "*Catalogue of Life*, including its synonyms. This way a species listed under an older name in one source "
        "and a newer name in another is counted once.",
        "",
        "The table shows which sources support the species on the list. Species supported by several sources are "
        "the most certain. Species that only one source supports deserve more caution: a single GBIF record, for "
        "instance, may be a misidentification or a one-off stray.",
        "",
        *_evidence_table(table),
        "",
        f"In total, {_n(single)} species ({_pct(single, total)}) rest on a single source, of which {_n(gbif_only)} "
        "on GBIF alone.",
        "",
        "## Barcodes: own and other",
        "",
        f"The barcodes counted are public sequences in BOLD of the standard animal barcode region ({markers}), at "
        f"least {min_length} bases long. Across the species on the list there are {_n(own_total + other_total)} such "
        f"sequences. {_n(own_total)} of them come from BGE's own projects, covering {_n(own_species)} species; the "
        f"other {_n(other_total)} were produced by others.",
        "",
    ]
    if own_total == 0 and (settings.own_projects or settings.own_institutions):
        lines += [
            "> **Check needed:** no barcodes were counted as BGE's own, although BGE projects are listed in the "
            "settings. This most likely means the projects are not recognised in this BOLD snapshot, not that "
            "BGE has no public barcodes.",
            "",
        ]

    lines += [
        "## Things to keep in mind",
        "",
        "**Some gaps may not be real gaps.** Not every name can be matched to the Catalogue of Life automatically: "
        "spelling variants, outdated names and names shared by two different species need a person to decide. "
        "Until someone has, barcodes filed under such a name do not count for any species, so the number of gaps "
        "is an upper limit. Names currently waiting for a decision:",
        "",
        "| Source | Names waiting |",
        "| --- | ---: |",
        f"| BOLD (these can hide existing barcodes) | {_n(review.get('bold', 0))} |",
        f"| The previous checklist | {_n(review.get('legacy', 0))} |",
        f"| GBIF | {_n(review.get('gbif', 0))} |",
        "",
        "The lists are in the folder `data/review/`; the BOLD list starts with the names that have the most "
        "specimens, which matter most.",
        "",
        f"**Names checked by experts, and names that are not.** The Catalogue of Life comes in two layers: an "
        "expert-curated *base release*, in which taxonomic editors have checked every name, and the *eXtended "
        "Release*, which adds names from many further sources automatically, without that check. This run uses "
        f"the {'eXtended' if release_type == 'xr' else 'base'} Release.",
        "",
    ]
    if release_type == "xr":
        lines += [
            f"{_n(len(xr))} species on the list ({_pct(len(xr), total)}) have a name that only the eXtended Release "
            "has. This says nothing about whether they occur in Europe (that is decided by the sources above); it "
            "means their name and place in the classification have not been checked by a Catalogue of Life "
            "editor. The largest groups among them: " + (_largest_orders(xr) or "none") + ". "
            "Which sources support them:",
            "",
            *_evidence_table(xr),
            "",
            f"The most doubtful are the {_n(xr_gbif_only)} that GBIF alone supports.",
        ]
    lines += [
        "",
        f"**Possibly alien species.** {_n(alien)} species have GBIF records in Europe that the data provider marked "
        "as introduced. They are on the list, but may not be native to Europe.",
        "",
        "**Only named species count.** Only BOLD specimens identified to a named species are counted. Specimens "
        "identified only to a higher group (such as a genus), or known only by a *BIN*, do not count for any "
        "species, even if they are in fact a species on this list.",
        "",
    ]
    rank_notes = [n for n in notes if " have no " in n]
    homonym_notes = [n for n in notes if "more than once" in n]
    if rank_notes:
        missing = [re.match(r"([\d,]+) species have no (\w+)", n).groups() for n in rank_notes]
        lines += [
            "**Incomplete classification.** For some species the Catalogue of Life gives no name at one of the "
            "levels shown on the website. Those cells are left empty, and in the table per group below these "
            "species appear as \"(none)\".",
            "",
            "| Level | Species without a name at that level |",
            "| --- | ---: |",
            *[f"| {level} | {count} |" for count, level in missing],
            "",
        ]
    if homonym_notes:
        lines += [
            "**Same name, different species.** Occasionally two different species in different groups carry the "
            "same name (homonyms). Each keeps its own row, told apart by its higher classification: "
            + " ".join(homonym_notes),
            "",
        ]

    lines += [
        "## Coverage per group",
        "",
        "Per class (a level of the classification, such as insects or birds): how many species are on the list, "
        "how many of them have a barcode, how many are gaps, and the share with a barcode. Largest groups first.",
        "",
        "| Phylum | Class | Common name | Species | With barcode | Gaps | With barcode (%) |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        *[
            f"| {r.phylum} | {r['class']} | {COMMON_NAMES.get(r['class'], '')} | {_n(r.species)} | {_n(r.barcoded)} | "
            f"{_n(r.gaps)} | {r.percent:.1f} |"
            for _, r in by_class.iterrows()
        ],
        "",
        "\"(none)\" means the Catalogue of Life gives no phylum or class for those species.",
        "",
        "## Data used in this run",
        "",
        "These are the exact versions used, so that the run can be repeated and cited. **Cite the DOIs** whenever "
        "the gap list is published or shared.",
        "",
        f"- **Catalogue of Life**, {'eXtended' if release_type == 'xr' else 'base'} Release {col_version}"
        + (f": https://doi.org/{col_doi}" if col_doi else ""),
        "- **The previous European checklist**: "
        + (f"https://github.com/bge-barcoding/gaplist-data/tree/{legacy}" if legacy else "not used"),
        "- **GBIF** occurrence download: " + (f"https://doi.org/{gbif_doi}" if gbif_doi else "not used"),
        f"- **BOLD** public data package: {'snapshot of ' + bold_snapshot if bold_snapshot else 'not used'}",
        f"- **Settings**: version code {fingerprint} (changes whenever any setting changes)",
        "",
        "## Glossary",
        "",
        "- **DNA barcode**: a short, standard stretch of DNA used to identify species. For animals it is part of "
        f"the COI gene, known as {markers}.",
        f"- **Barcode-compliant**: a barcode sequence of at least {min_length} bases, the quality agreed for this "
        "list.",
        "- **Gap**: a European species with no public barcode-compliant sequence yet.",
        "- **Catalogue of Life**: the global list of accepted species names and their synonyms, used here to link "
        "the names from all sources.",
        "- **Base release** and **eXtended Release**: the expert-curated core of the Catalogue of Life, and the "
        "larger version with names added automatically.",
        "- **GBIF**: the Global Biodiversity Information Facility, which brings together records of where species "
        "have been observed or collected.",
        "- **BOLD**: the Barcode of Life Data System, the main public database of DNA barcodes.",
        "- **BIN**: a Barcode Index Number, BOLD's grouping of similar barcodes that often, but not always, "
        "corresponds to a species.",
        "",
    ]
    return "\n".join(lines)
