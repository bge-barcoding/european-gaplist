"""Match names from any source to Catalogue of Life species.

Every name gets exactly one outcome:

==================  =========================================================
exact               the name is an accepted CoL name (species or below)
synonym             the name is a CoL synonym of exactly one species
disambiguated       several CoL species share the name; the family, order,
                    class or phylum given by the source picked one
alternative_name    the name itself did not match, but alternative names
                    given by the source (e.g. its own synonyms) all point
                    to the same CoL species
curated             decided by a person in config/curation.tsv
review              needs a person: near matches, unresolved homonyms and
                    uncertain identifications ("cf."); a suggestion is
                    given where there is one
unmatched           no CoL name found, not even a near match
not_a_species       hybrids, placeholders and other names that cannot be
                    matched to a species
rejected            ruled out by a person in config/curation.tsv
==================  =========================================================

Only exact, synonym, disambiguated, alternative_name and curated names count
as resolved. Subspecies and varieties are counted with their species.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from .names import parse

RESOLVED = ("exact", "synonym", "disambiguated", "alternative_name", "curated")
HINT_RANKS = ("family", "order", "class", "phylum")


@dataclass
class Query:
    source: str
    original_name: str
    hints: dict[str, str | None]
    alternatives: tuple[str, ...] = ()


# CoL writes species in a subgenus as "Lithobius (Lithobius) forficatus";
# source names are matched without the subgenus, so CoL's are too.
PLAIN = "trim(regexp_replace({col}, '\\s*\\([^)]*\\)', '', 'g'))"


def _candidate_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Lookup tables: every name that leads to a species, accepted or synonym."""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE accepted_names AS
        SELECT {PLAIN.format(col="name")} AS name, species_id, family, "order", class, phylum
        FROM taxon WHERE species_id IS NOT NULL;

        CREATE OR REPLACE TEMP TABLE synonym_names AS
        SELECT {PLAIN.format(col="s.name")} AS name, s.synonym_id, t.species_id,
               t.family, t."order", t.class, t.phylum
        FROM synonym s JOIN taxon t ON t.taxon_id = s.accepted_id
        WHERE t.species_id IS NOT NULL;

        CREATE OR REPLACE TEMP TABLE species_epithets AS
        SELECT taxon_id AS species_id, name, split_part(plain, ' ', 1) AS genus,
               split_part(plain, ' ', 2) AS epithet
        FROM (SELECT *, {PLAIN.format(col="name")} AS plain FROM taxon WHERE rank = 'species');
        """
    )


def _lookup(con, table: str, names: pd.DataFrame) -> pd.DataFrame:
    """All candidate species for each (qid, name) row, from one lookup table."""
    if names.empty:
        return pd.DataFrame(columns=["qid", "species_id", "synonym_id", *HINT_RANKS])
    con.register("lookup_names", names)
    synonym_col = "c.synonym_id" if table == "synonym_names" else "NULL"
    found = con.execute(
        f"""
        SELECT n.qid, c.species_id, {synonym_col} AS synonym_id, c.family, c."order", c.class, c.phylum
        FROM lookup_names n JOIN {table} c ON c.name = n.name
        """
    ).df()
    con.unregister("lookup_names")
    return found


def _choose(candidates: pd.DataFrame, hints: dict[str, str | None]) -> tuple[str | None, list[str], bool]:
    """Pick one species from candidates. Returns (species, all species, used hints)."""
    species = list(dict.fromkeys(candidates["species_id"]))
    if len(species) == 1:
        return species[0], species, False
    for rank in HINT_RANKS:
        hint = (hints.get(rank) or "").strip().lower()
        if not hint:
            continue
        agreeing = candidates[candidates[rank].fillna("").str.lower() == hint]
        chosen = list(dict.fromkeys(agreeing["species_id"]))
        if len(chosen) == 1:
            return chosen[0], species, True
    return None, species, False


def _near_matches(con, rows: pd.DataFrame) -> pd.DataFrame:
    """Species in the same genus whose epithet differs by at most two letters."""
    if rows.empty:
        return pd.DataFrame(columns=["qid", "species_id", "distance"])
    con.register("near_names", rows)
    found = con.execute(
        """
        SELECT n.qid, s.species_id, levenshtein(n.epithet, s.epithet) AS distance
        FROM near_names n JOIN species_epithets s ON s.genus = n.genus
        WHERE levenshtein(n.epithet, s.epithet) <= CASE WHEN length(n.epithet) >= 6 THEN 2 ELSE 1 END
          AND s.epithet <> n.epithet
        ORDER BY n.qid, distance, s.name
        """
    ).df()
    con.unregister("near_names")
    return found


def resolve(con: duckdb.DuckDBPyConnection, queries: list[Query], curation: list[dict[str, str]]) -> pd.DataFrame:
    """Resolve names and return one row per query (not yet stored)."""
    _candidate_tables(con)
    parsed = [parse(q.original_name) for q in queries]
    results: list[dict] = [
        {
            "source": q.source,
            "original_name": q.original_name,
            "canonical_name": p.canonical,
            "outcome": None if p.is_species_name else "not_a_species",
            "taxon_id": None,
            "via_synonym_id": None,
            "candidates": [],
            "note": "; ".join(p.notes),
        }
        for q, p in zip(queries, parsed)
    ]

    def open_ids() -> list[int]:
        return [i for i, r in enumerate(results) if r["outcome"] is None]

    def note(i: int, text: str) -> None:
        results[i]["note"] = "; ".join(x for x in (results[i]["note"], text) if x)

    # 1 and 2: the full name (with subspecies), then the binomial alone,
    #          first among accepted names, then among synonyms.
    for table, outcome in (("accepted_names", "exact"), ("synonym_names", "synonym")):
        for use_binomial in (False, True):
            ids = open_ids()
            names = pd.DataFrame(
                [
                    (i, parsed[i].binomial if use_binomial else parsed[i].canonical)
                    for i in ids
                    if not use_binomial or parsed[i].infra
                ],
                columns=["qid", "name"],
            )
            found = _lookup(con, table, names)
            for qid, group in found.groupby("qid"):
                chosen, species, used_hints = _choose(group, queries[qid].hints)
                if use_binomial:
                    note(qid, "matched on species, subspecies or variety not found")
                if chosen:
                    via = group.loc[group.species_id == chosen, "synonym_id"].iloc[0]
                    results[qid].update(
                        outcome="disambiguated" if used_hints else outcome,
                        taxon_id=chosen,
                        via_synonym_id=None if pd.isna(via) else via,
                    )
                else:
                    results[qid].update(outcome="review", candidates=species)
                    note(qid, f"{len(species)} CoL species share this name; the source's classification does not decide")

    # 3: alternative names given by the source (e.g. its own synonym list).
    alt_rows = [
        (i, parse(alt).canonical)
        for i in open_ids()
        for alt in queries[i].alternatives
        if parse(alt).canonical
    ]
    alt_names = pd.DataFrame(alt_rows, columns=["qid", "name"])
    found = pd.concat([_lookup(con, "accepted_names", alt_names), _lookup(con, "synonym_names", alt_names)])
    for qid, group in found.groupby("qid"):
        chosen, species, _ = _choose(group, queries[qid].hints)
        if chosen:
            results[qid].update(outcome="alternative_name", taxon_id=chosen)
            note(qid, "matched through a name the source lists as a synonym")

    # 4: near matches (spelling, gender endings) are never accepted automatically.
    near_rows = pd.DataFrame(
        [(i, parsed[i].genus, parsed[i].epithet) for i in open_ids()], columns=["qid", "genus", "epithet"]
    )
    for qid, group in _near_matches(con, near_rows).groupby("qid"):
        results[qid].update(outcome="review", candidates=list(dict.fromkeys(group["species_id"])))
        note(qid, "near match: spelling differs")

    for i in open_ids():
        results[i]["outcome"] = "unmatched"

    # 5: uncertain identifications ("cf.") always go to a person.
    for i, p in enumerate(parsed):
        if p.uncertain and results[i]["outcome"] in RESOLVED:
            results[i].update(outcome="review", candidates=[results[i]["taxon_id"]], taxon_id=None)

    _apply_curation(con, results, curation)
    return pd.DataFrame(results)


def _apply_curation(con, results: list[dict], curation: list[dict[str, str]]) -> None:
    decisions = {(c["source"], c["original_name"]): c for c in curation}
    for row in results:
        decision = decisions.get((row["source"], row["original_name"]))
        if not decision:
            continue
        who = f"decided by {decision['curator'] or 'curator'} {decision['date']}".strip()
        if decision["decision"] == "reject":
            row.update(outcome="rejected", taxon_id=None)
        elif decision["decision"] == "accept":
            if row["outcome"] in RESOLVED:
                pass
            elif row["candidates"]:
                row.update(outcome="curated", taxon_id=row["candidates"][0])
            else:
                row["note"] += "; curation says accept, but there is no suggestion to accept"
                continue
        elif decision["decision"] == "map":
            target = parse(decision["target_name"]).canonical
            hits = con.execute(
                "SELECT DISTINCT species_id FROM accepted_names WHERE name = ? "
                "UNION SELECT DISTINCT species_id FROM synonym_names WHERE name = ?",
                [target, target],
            ).fetchall()
            if len(hits) != 1:
                row.update(outcome="review")
                row["note"] += f"; curation target '{decision['target_name']}' not found as one CoL species"
                continue
            row.update(outcome="curated", taxon_id=hits[0][0])
        row["note"] = "; ".join(x for x in (row["note"], who, decision.get("note", "")) if x)


def store(con: duckdb.DuckDBPyConnection, results: pd.DataFrame) -> None:
    """Replace this source's rows in name_resolution."""
    for source in results["source"].unique():
        con.execute("DELETE FROM name_resolution WHERE source = ?", [source])
    con.register("resolution_df", results)
    con.execute(
        """
        INSERT INTO name_resolution
        SELECT source, original_name, canonical_name, outcome, taxon_id, via_synonym_id,
               CAST(candidates AS VARCHAR[]), note
        FROM resolution_df
        """
    )
    con.unregister("resolution_df")
