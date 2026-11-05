import zipfile
from pathlib import Path

import duckdb
import pytest

from gaplist import backbone, col_source, paths
from gaplist.config import load_settings

# A tiny Catalogue of Life in ColDP NameUsage form (headers prefixed "col:", as in COL downloads).
NAME_USAGE = """\
col:ID\tcol:parentID\tcol:status\tcol:rank\tcol:scientificName\tcol:authorship\tcol:extinct
1\t\taccepted\tkingdom\tAnimalia\t\t
2\t1\taccepted\tphylum\tArthropoda\t\t
3\t2\taccepted\tclass\tInsecta\t\t
4\t3\taccepted\torder\tDiptera\t\t
5\t4\taccepted\tfamily\tChironomidae\t\t
6\t5\taccepted\tgenus\tAagaardia\tSaether, 2000\t
7\t6\taccepted\tspecies\tAagaardia protensa\t(Brundin, 1947)\t
8\t7\taccepted\tsubspecies\tAagaardia protensa minor\tDoe, 2001\t
9\t6\tprovisionally accepted\tspecies\tAagaardia sivertseni\t(Saether, 1979)\t
10\t7\tsynonym\tspecies\tAagaardia oldname\tRoe, 1950\t
19\t9\tambiguous synonym\tspecies\tAagaardia dubia\t\t
18\t6\tbare name\tspecies\tAagaardia nudum\t\t
11\t4\taccepted\tgenus\tOrphanus\t\t
12\t11\taccepted\tspecies\tOrphanus solus\t\t
13\t5\taccepted\tgenus\tFossilia\t\ttrue
14\t13\taccepted\tspecies\tFossilia antiqua\t\t
15\t\taccepted\tkingdom\tPlantae\t\t
16\t15\taccepted\tspecies\tRosa canina\tL.\t
17\t16\tsynonym\tspecies\tRosa vulgaris\t\t
"""

METADATA = "title: Catalogue of Life (test)\nversion: 2026-10-10\ndoi: 10.48580/test\n"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(paths, "data_dir", lambda root=None: data)
    manual = data / "col" / "manual"
    manual.mkdir(parents=True)
    with zipfile.ZipFile(manual / "test_coldp.zip", "w") as archive:
        archive.writestr("metadata.yaml", METADATA)
        archive.writestr("NameUsage.tsv", NAME_USAGE)
    return data


def run(workspace: Path, **col_overrides):
    settings = load_settings()
    settings.col = {**settings.col, **col_overrides}
    result = backbone.build_backbone(settings, workspace / "gaplist.duckdb")
    con = duckdb.connect(str(workspace / "gaplist.duckdb"))
    return result, con


def test_manual_file_is_used_and_described(workspace):
    release = col_source.fetch({"release_type": "base", "version": "latest"})
    assert release.path.name == "test_coldp.zip"
    assert release.version == "2026-10-10"
    assert release.doi == "10.48580/test"


def test_backbone_contents(workspace):
    result, con = run(workspace)
    assert result.ok, result.message
    species = {r[0] for r in con.execute("SELECT name FROM taxon WHERE rank = 'species'").fetchall()}
    # extinct genus, bare name and other kingdoms are left out
    assert species == {"Aagaardia protensa", "Aagaardia sivertseni", "Orphanus solus"}
    assert "3 species in Animalia" in result.message


def test_fixed_ranks_and_species_link(workspace):
    _, con = run(workspace)
    row = con.execute(
        """SELECT kingdom, phylum, class, "order", family, genus, species, species_id
           FROM taxon WHERE name = 'Aagaardia protensa minor'"""
    ).fetchone()
    assert row == ("Animalia", "Arthropoda", "Insecta", "Diptera", "Chironomidae", "Aagaardia",
                   "Aagaardia protensa", "7")
    assert con.execute("SELECT family FROM taxon WHERE name = 'Orphanus solus'").fetchone() == (None,)


def test_synonyms_point_to_accepted_names(workspace):
    _, con = run(workspace)
    rows = set(con.execute("SELECT name, status, accepted_id FROM synonym").fetchall())
    assert rows == {("Aagaardia oldname", "synonym", "7"), ("Aagaardia dubia", "ambiguous synonym", "9")}


def test_nested_sets_are_consistent(workspace):
    _, con = run(workspace)
    bad = con.execute(
        """SELECT count(*) FROM taxon c JOIN taxon p ON c.parent_id = p.taxon_id
           WHERE NOT (p.lft < c.lft AND c.rgt < p.rgt)"""
    ).fetchone()[0]
    assert bad == 0
    n = con.execute("SELECT count(*) FROM taxon").fetchone()[0]
    assert con.execute("SELECT min(lft), max(rgt) FROM taxon").fetchone() == (1, 2 * n)
    # every species sits inside the kingdom's interval
    assert con.execute(
        "SELECT count(*) FROM taxon t, taxon k WHERE k.name = 'Animalia' AND NOT (t.lft BETWEEN k.lft AND k.rgt)"
    ).fetchone()[0] == 0


def test_run_is_recorded_and_rebuild_replaces(workspace):
    run(workspace)[1].close()
    result, con = run(workspace)
    assert "Run 2" in result.message
    assert con.execute("SELECT count(*) FROM taxon WHERE rank = 'species'").fetchone()[0] == 3
    assert con.execute("SELECT col_version, col_doi FROM run WHERE run_id = 2").fetchone() == (
        "2026-10-10", "10.48580/test")


def test_extinct_can_be_included(workspace):
    result, con = run(workspace, exclude_extinct=False)
    assert result.ok
    assert con.execute("SELECT count(*) FROM taxon WHERE name = 'Fossilia antiqua'").fetchone()[0] == 1


def test_unknown_kingdom_is_reported_plainly(workspace):
    result, _ = run(workspace, kingdoms=["Animalia", "Fungi"])
    assert not result.ok
    assert "kingdom 'Fungi' does not occur" in result.message


def test_two_manual_files_are_refused(workspace):
    (workspace / "col" / "manual" / "other.zip").write_bytes(b"")
    result, _ = run(workspace)
    assert not result.ok
    assert "more than one zip file" in result.message
