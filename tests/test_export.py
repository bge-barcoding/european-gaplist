import zipfile

import pandas as pd
import pytest

from gaplist import backbone, db, export, paths
from gaplist.config import load_settings

from .test_backbone import METADATA, NAME_USAGE


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda root=None: data)
    (data / "col" / "manual").mkdir(parents=True)
    with zipfile.ZipFile(data / "col" / "manual" / "t.zip", "w") as archive:
        archive.writestr("metadata.yaml", METADATA)
        archive.writestr("NameUsage.tsv", NAME_USAGE)
    assert backbone.build_backbone(load_settings(), data / "g.duckdb").ok
    con = db.connect(data / "g.duckdb")
    # species 7 (Aagaardia protensa): legacy + GBIF + BOLD, barcoded; 9: GBIF only, possibly alien, no barcode;
    # 12 (Orphanus solus, no family): legacy only, no barcode
    con.executemany(
        "INSERT INTO evidence (taxon_id, source, source_detail, record_count, possibly_alien) VALUES (?, ?, ?, ?, ?)",
        [("7", "legacy", "BOLD,FE,SyDip", 1, False), ("7", "gbif", "40 records", 40, False),
         ("7", "bold", "2 specimens", 2, False), ("9", "gbif", "5 records", 5, True),
         ("12", "legacy", "LF", 1, False)],
    )
    con.execute("INSERT INTO barcode_status VALUES ('7', 3, 2, 1, 1, 1, 2)")
    con.close()
    return data


def test_seed_and_full_table(workspace):
    result = export.export(load_settings(), workspace / "g.duckdb")
    assert result.ok, result.message
    assert "3 European species on the target list; 2 of them are gaps" in result.message
    seed = pd.read_csv(workspace / "output" / "targetlist_seed.tsv", sep="\t", dtype=str, keep_default_na=False)
    assert list(seed.columns) == export.SEED_COLUMNS
    rows = {r.Species: r for r in seed.itertuples()}
    protensa = rows["Aagaardia protensa"]
    assert (protensa.SpeciesLocality, protensa.SpeciesOccurrenceStatus, protensa.OwnBarcodes,
            protensa.OtherBarcodes) == ("GBIF;BOLD;BOLD,FE,SyDip", "", "1", "1")
    assert rows["Aagaardia sivertseni"].SpeciesOccurrenceStatus == "gap"
    assert rows["Orphanus solus"].Family == ""
    assert set(seed.Wanted) == {"1"} and set(seed.Collected) == {"0"}
    full = pd.read_csv(workspace / "output" / "gaplist_full.tsv", sep="\t")
    assert bool(full.set_index("species").loc["Aagaardia sivertseni", "possibly_alien"])
    summary = (workspace / "output" / "summary.md").read_text()
    assert "European species: 3" in summary and "Gaps (no compliant barcode): 2" in summary
    assert "1 species have no family" in result.message


def test_min_sources_and_priority_groups(workspace):
    settings = load_settings()
    settings.evidence = {"min_sources": 2}
    settings.target_list = {**settings.target_list,
                            "wanted": {"default": 1, "priority": 2, "priority_groups": [{"family": "Chironomidae"}]}}
    result = export.export(settings, workspace / "g.duckdb")
    assert result.ok, result.message
    seed = pd.read_csv(workspace / "output" / "targetlist_seed.tsv", sep="\t", dtype=str)
    assert list(seed.Species) == ["Aagaardia protensa"]  # the only species with two or more sources
    assert list(seed.Wanted) == ["2"]


def test_xr_only_can_be_left_out(workspace):
    con = db.connect(workspace / "g.duckdb")
    con.execute("UPDATE taxon SET xr_added = true WHERE taxon_id = '12'")
    con.close()
    settings = load_settings()
    settings.target_list = {**settings.target_list, "include_xr_only": False}
    seed = export.seed_rows(export.build_table(db.connect(workspace / "g.duckdb"), settings), settings)
    assert "Orphanus solus" not in set(seed.Species)


def test_checks_stop_bad_output():
    seed = pd.DataFrame([["Animalia", "", "", "", "", "", "", "", "gap", 0, 1, 0, -1]], columns=export.SEED_COLUMNS)
    problems, _ = export.check_seed(seed)
    assert any("no species name" in p for p in problems)
    assert any("OtherBarcodes" in p for p in problems)
