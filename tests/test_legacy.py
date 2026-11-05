import zipfile

import duckdb
import pandas as pd
import pytest

from gaplist import backbone, legacy, paths
from gaplist.config import load_settings

from .test_backbone import METADATA, NAME_USAGE

GAPLIST = (
    "species;Phylum;Class;Order;Family;source;speciemens barcoded;speciemens;public BINs;verified by;status;"
    "BOLD taxid;BOLD taxid 1;BOLD taxid 2;;;;;;\n"
    "Chironomidae;;;;;;;;;;;;;;;;;;;\n"
    "Aagaardia protensa;Arthropoda;Insecta;Diptera;Chironomidae;BOLD,FE,SyDip;2;3;1;;gap;731420;;;;;;;;\n"
    "Aagaardia oldname;Arthropoda;Insecta;Diptera;Chironomidae;FE;;;;;gap;;;;;;;;;\n"
    "Aagaardia sivertzeni;Arthropoda;Insecta;Diptera;Chironomidae;SyDip;;;;;gap;;;;;;;;;\n"
    "Orphanus solus;Arthropoda;Insecta;Diptera;;LF;;;;;gap;;;;;;;;;\n"
    "Arion ater x Arion rufus;Mollusca;Gastropoda;Stylommatophora;Arionidae;BOLD;;;;;gap;;;;;;;;;\n"
).encode("utf-8") + "Orphänus solus;Arthropoda;Insecta;Diptera;;DTN;;;;;gap;;;;;;;;;\n".encode("cp1252")
SYNONYMS = "Aagaardia protensa;Aagaardia oldname;\nOrphanus solus;\n"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda root=None: data)
    (data / "col" / "manual").mkdir(parents=True)
    with zipfile.ZipFile(data / "col" / "manual" / "t.zip", "w") as archive:
        archive.writestr("metadata.yaml", METADATA)
        archive.writestr("NameUsage.tsv", NAME_USAGE)
    manual = data / "legacy" / "manual"
    manual.mkdir(parents=True)
    (manual / "Gap_list_all_updated.csv").write_bytes(GAPLIST)
    (manual / "all_specs_and_syn.csv").write_text(SYNONYMS)
    return data


def test_needs_backbone_first(workspace):
    result = legacy.import_legacy(load_settings(), workspace / "g.duckdb")
    assert not result.ok and "Run section 1 first" in result.message


def test_import(workspace):
    settings = load_settings()
    assert backbone.build_backbone(settings, workspace / "g.duckdb").ok
    result = legacy.import_legacy(settings, workspace / "g.duckdb")
    assert result.ok, result.message
    assert "6 distinct species names" in result.message

    con = duckdb.connect(str(workspace / "g.duckdb"))
    outcomes = dict(con.execute("SELECT original_name, outcome FROM name_resolution").fetchall())
    assert outcomes["Aagaardia protensa"] == "exact"
    assert outcomes["Aagaardia oldname"] == "synonym"
    assert outcomes["Aagaardia sivertzeni"] == "review"
    assert outcomes["Arion ater x Arion rufus"] == "not_a_species"
    assert outcomes["Orph\u00e4nus solus"] == "exact"  # Windows-encoded line, diacritic removed

    evidence = dict(con.execute("SELECT taxon_id, source_detail FROM evidence WHERE source = 'legacy'").fetchall())
    assert evidence["7"] == "BOLD,FE,SyDip"  # protensa and its synonym merge onto one species
    assert con.execute("SELECT legacy_commit FROM run").fetchone()[0] == settings.legacy["commit"]

    review = pd.read_excel(workspace / "review" / "legacy_names.xlsx", sheet_name="Names to review")
    row = review[review.original_name == "Aagaardia sivertzeni"].iloc[0]
    assert row.suggestion == "Aagaardia sivertseni"
    assert list(review.columns[:6]) == ["source", "original_name", "decision", "target_name", "curator", "date"]
