import duckdb
import pytest

from gaplist import db
from gaplist.resolve import Query, resolve, store

# taxon_id, parent, rank, name, family, order, class, phylum, species_id
TAXA = [
    ("s1", "g1", "species", "Aagaardia protensa", "Chironomidae", "Diptera", "Insecta", "Arthropoda", "s1"),
    ("s1a", "s1", "subspecies", "Aagaardia protensa minor", "Chironomidae", "Diptera", "Insecta", "Arthropoda", "s1"),
    ("s2", "g1", "species", "Aagaardia sivertseni", "Chironomidae", "Diptera", "Insecta", "Arthropoda", "s2"),
    ("s3", "g2", "species", "Polyommatus icarus", "Lycaenidae", "Lepidoptera", "Insecta", "Arthropoda", "s3"),
    ("s4", "g3", "species", "Tipula lunata", "Tipulidae", "Diptera", "Insecta", "Arthropoda", "s4"),
    # a homonym: the same binomial in two families
    ("h1", "g4", "species", "Duplex communis", "Carabidae", "Coleoptera", "Insecta", "Arthropoda", "h1"),
    ("h2", "g5", "species", "Duplex communis", "Pyralidae", "Lepidoptera", "Insecta", "Arthropoda", "h2"),
    ("s5", "g6", "species", "Cryptocephalus eridani", "Chrysomelidae", "Coleoptera", "Insecta", "Arthropoda", "s5"),
    ("s7", "g8", "species", "Lithobius (Lithobius) forficatus", "Lithobiidae", "Lithobiomorpha", "Chilopoda",
     "Arthropoda", "s7"),
    ("s6", "g7", "species", "Lycaena helle", "Lycaenidae", "Lepidoptera", "Insecta", "Arthropoda", "s6"),
]
SYNONYMS = [("y1", "Aagaardia oldname", "synonym", "s1"), ("y2", "Lycaena amphidamas", "synonym", "s6")]


@pytest.fixture
def con(tmp_path):
    con = db.connect(tmp_path / "t.duckdb")
    for t in TAXA:
        con.execute(
            'INSERT INTO taxon (taxon_id, parent_id, rank, name, family, "order", class, phylum, species_id) '
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            list(t),
        )
    for s in SYNONYMS:
        con.execute("INSERT INTO synonym (synonym_id, name, status, accepted_id) VALUES (?, ?, ?, ?)", list(s))
    return con


def q(name, family=None, order=None, alternatives=()):
    return Query("test", name, {"family": family, "order": order, "class": None, "phylum": None}, alternatives)


def outcome(con, query, curation=()):
    row = resolve(con, [query], list(curation)).iloc[0]
    return row.outcome, row.taxon_id, list(row.candidates)


def test_exact(con):
    assert outcome(con, q("Aagaardia protensa"))[:2] == ("exact", "s1")


def test_subgenus_and_subspecies_count_with_species(con):
    assert outcome(con, q("Aagaardia (Aagaardia) protensa"))[:2] == ("exact", "s1")
    assert outcome(con, q("Aagaardia protensa minor"))[:2] == ("exact", "s1")
    assert outcome(con, q("Aagaardia protensa nonexistens"))[:2] == ("exact", "s1")


def test_col_subgenus_is_ignored(con):
    assert outcome(con, q("Lithobius forficatus"))[:2] == ("exact", "s7")
    assert outcome(con, q("Lithobius (Monotarsobius) forficatus"))[:2] == ("exact", "s7")
    assert outcome(con, q("Lithobius forficata")) == ("review", None, ["s7"])


def test_synonym(con):
    result = resolve(con, [q("Aagaardia oldname")], [])
    assert (result.outcome[0], result.taxon_id[0], result.via_synonym_id[0]) == ("synonym", "s1", "y1")


def test_homonym_resolved_by_family_or_order(con):
    assert outcome(con, q("Duplex communis", family="Pyralidae"))[:2] == ("disambiguated", "h2")
    assert outcome(con, q("Duplex communis", order="Coleoptera"))[:2] == ("disambiguated", "h1")


def test_homonym_without_hint_goes_to_review(con):
    result, taxon, candidates = outcome(con, q("Duplex communis", family="Unknownidae"))
    assert result == "review" and taxon is None and set(candidates) == {"h1", "h2"}


def test_spelling_and_gender_go_to_review_with_suggestion(con):
    assert outcome(con, q("Aagaardia protenza")) == ("review", None, ["s1"])
    assert outcome(con, q("Tipula lunatus")) == ("review", None, ["s4"])


def test_alternative_names(con):
    assert outcome(con, q("Lycaena nomen", alternatives=("Lycaena amphidamas",)))[:2] == ("alternative_name", "s6")


def test_uncertain_identification_goes_to_review(con):
    assert outcome(con, q("Cryptocephalus cfr. eridani")) == ("review", None, ["s5"])


def test_not_a_species_and_unmatched(con):
    assert outcome(con, q("Arion ater x Arion rufus"))[0] == "not_a_species"
    assert outcome(con, q("Nusquam inventus"))[0] == "unmatched"


def test_curation(con):
    cur = lambda name, decision, target="": {  # noqa: E731
        "source": "test", "original_name": name, "decision": decision, "target_name": target,
        "curator": "RV", "date": "2026-11-05", "note": "",
    }
    assert outcome(con, q("Aagaardia protenza"), [cur("Aagaardia protenza", "accept")])[:2] == ("curated", "s1")
    assert outcome(con, q("Nusquam inventus"), [cur("Nusquam inventus", "map", "Tipula lunata")])[:2] == ("curated", "s4")
    assert outcome(con, q("Aagaardia protensa"), [cur("Aagaardia protensa", "reject")])[:2] == ("rejected", None)
    assert outcome(con, q("Nusquam inventus"), [cur("Nusquam inventus", "map", "Nonexistent name")])[0] == "review"


def test_store_replaces_rows(con):
    store(con, resolve(con, [q("Aagaardia protensa"), q("Nusquam inventus")], []))
    store(con, resolve(con, [q("Aagaardia protensa")], []))
    assert con.execute("SELECT count(*) FROM name_resolution").fetchone()[0] == 1
