"""Turn a name as written in a source into a canonical name for matching.

Source lists are written by hand and contain much more than clean
binomials: subgenera in brackets, subspecies and varieties, qualifiers such
as "cf." or "s.l.", hybrids, and placeholders for undescribed species. This
module recognises those forms and says what it did, so that every decision
can be explained in the review lists.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Words that say an identification is uncertain: the name is matched, but a
# person should confirm it.
UNCERTAIN = {"cf", "cf.", "cfr", "cfr.", "aff", "aff."}
# Words that widen or narrow a species concept; they are dropped.
SENSU = {"s.l.", "sl.", "sl", "s.lat.", "s.s.", "ss.", "s.str.", "sensu", "lato", "stricto", "str.",
         "agg", "agg.", "aggr", "aggr.", "group", "grp", "grp.", "complex", "parth.", "parth"}
# Markers in front of an infraspecific epithet; they are dropped, the epithet is kept.
INFRA_MARKERS = {"var.", "var", "f.", "fo.", "forma", "ssp.", "ssp", "subsp.", "subsp", "morph", "ab."}
HYBRID = {"x", "×"}
# Words that mean "an unnamed species"; such names cannot be matched.
UNNAMED = {"sp", "sp.", "spp", "spp.", "sp.nov.", "nov.", "indet", "indet."}
GENUS = re.compile(r"^[A-Z][a-z]+(?:-[a-z]+)?$")
EPITHET = re.compile(r"^[a-z]+(?:-[a-z]+)?$")


@dataclass
class ParsedName:
    original: str
    canonical: str | None  # genus + epithet(s), or None when not a species name
    genus: str | None = None
    epithet: str | None = None
    infra: str | None = None
    uncertain: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def binomial(self) -> str | None:
        return f"{self.genus} {self.epithet}" if self.genus and self.epithet else None

    @property
    def is_species_name(self) -> bool:
        return self.canonical is not None


def _ascii(text: str) -> str:
    """Remove diacritics: 'steinböcki' becomes 'steinbocki'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def parse(raw: str) -> ParsedName:
    original = raw
    notes: list[str] = []
    text = " ".join(raw.replace(" ", " ").split())

    if "?" in text:
        notes.append("question mark in source")
        text = text.replace("?", "")
    if re.search(r"\([^)]*\)", text):
        notes.append("subgenus or remark in brackets removed")
        text = re.sub(r"\s*\([^)]*\)", "", text)
    text = text.replace("incertae sedis", "")
    plain = _ascii(text)
    if plain != text:
        notes.append("diacritics removed")

    tokens = plain.split()
    lowered = [t.lower() for t in tokens]

    def not_species(reason: str) -> ParsedName:
        return ParsedName(original, None, notes=notes + [reason])

    if any(t in HYBRID for t in lowered):
        return not_species("hybrid")
    if any(t.startswith("bold:") for t in lowered):
        return not_species("placeholder (BOLD BIN)")
    if len(tokens) < 2:
        return not_species("genus only")
    if not GENUS.match(tokens[0]):
        return not_species("first word is not a genus name")

    genus, rest = tokens[0], tokens[1:]
    uncertain = False
    words: list[str] = []
    for token, low in zip(rest, (t.lower() for t in rest)):
        if low in UNCERTAIN:
            uncertain = True
            notes.append(f"'{token}' (uncertain identification)")
        elif low in SENSU:
            notes.append(f"'{token}' removed")
        elif low in INFRA_MARKERS:
            notes.append(f"'{token}' removed")
        elif low in UNNAMED:
            return not_species("unnamed species (sp.)")
        else:
            words.append(token)

    if not words:
        return not_species("no species epithet")
    if not EPITHET.match(words[0]):
        return not_species("placeholder, not a species epithet")
    epithet = words[0]
    infra = None
    if len(words) > 1:
        if EPITHET.match(words[1]):
            infra = words[1]
        if len(words) > (2 if infra else 1):
            notes.append(f"trailing words ignored: {' '.join(words[2 if infra else 1:])}")

    canonical = " ".join(w for w in (genus, epithet, infra) if w)
    return ParsedName(original, canonical, genus, epithet, infra, uncertain, notes)
