import zipfile

import duckdb
import pytest

from gaplist import backbone, bold, paths
from gaplist.config import load_settings

from .test_backbone import METADATA, NAME_USAGE

COLUMNS = [
    "processid", "sampleid", "inst", "bin_uri", "kingdom", "phylum", "class", "order", "family", "species",
    "identification_rank", "country_iso", "marker_code", "nuc_basecount", "bold_recordset_code_arr", "nuc",
]
ROWS = [
    # a misspelt name, two specimens: goes to review with a suggestion
    ["P9", "S9", "CBG", "NA", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia protenza", "species", "NO", "COI-5P", "300", "NA", "ACGT"],
    ["P10", "S10", "CBG", "NA", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia protenza", "species", "NO", "COI-5P", "300", "NA", "ACGT"],
    # protensa, Netherlands, compliant, in an "own" project
    ["P1", "S1", "Naturalis Biodiversity Center", "BOLD:AAA0001", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia protensa", "species", "NL", "COI-5P", "658", "BGENL,DS-TEST", "ACGT"],
    # a subspecies identification, Germany, too short to be compliant
    ["P2", "S2", "ZFMK", "BOLD:AAA0001", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia protensa", "subspecies", "DE", "COI-5P", "400", "GBOL", "ACGT"],
    # sivertseni, Canada: compliant but not European
    ["P3", "S3", "CBG", "BOLD:AAA0002", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia sivertseni", "species", "CA", "COI-5P", "650", "CBGX", "ACGT"],
    # identified to genus only: not placed on a species
    ["P4", "S4", "CBG", "BOLD:AAA0003", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "NA", "genus", "SE", "COI-5P", "655", "NA", "ACGT"],
    # own by institution, France
    ["P5", "S5", "Naturalis Biodiversity Center", "BOLD:AAA0004", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "NA", "Orphanus solus", "species", "FR", "COI-5P", "520", "NA", "ACGT"],
    # a plant: wrong kingdom
    ["P6", "S6", "X", "NA", "Plantae", "Tracheophyta", "Magnoliopsida", "Rosales",
     "Rosaceae", "Rosa canina", "species", "NL", "COI-5P", "650", "NA", "ACGT"],
    # wrong marker
    ["P7", "S7", "X", "NA", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia protensa", "species", "NL", "COI-3P", "650", "NA", "ACGT"],
    # filed under a synonym, collected in Russia (not in the Europe list)
    ["P8", "S8", "ZIN", "BOLD:AAA0005", "Animalia", "Arthropoda", "Insecta", "Diptera",
     "Chironomidae", "Aagaardia oldname", "species", "RU", "COI-5P", "600", "NA", "ACGT"],
]
TSV = "\t".join(COLUMNS) + "\n" + "".join("\t".join(r) + "\n" for r in ROWS)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda root=None: data)
    (data / "col" / "manual").mkdir(parents=True)
    with zipfile.ZipFile(data / "col" / "manual" / "t.zip", "w") as archive:
        archive.writestr("metadata.yaml", METADATA)
        archive.writestr("NameUsage.tsv", NAME_USAGE)
    (data / "bold" / "manual").mkdir(parents=True)
    assert backbone.build_backbone(load_settings(), data / "g.duckdb").ok
    return data


def settings_with_own():
    settings = load_settings()
    settings.own_projects = ["BGENL"]
    settings.own_institutions = ["Naturalis Biodiversity Center"]
    return settings


def check_results(workspace, result):
    assert result.ok, result.message
    con = duckdb.connect(str(workspace / "g.duckdb"))
    status = {r[0]: r[1:] for r in con.execute(
        "SELECT taxon_id, specimens, compliant, european_compliant, own, other, bins FROM barcode_status").fetchall()}
    assert status == {
        "7": (3, 2, 1, 1, 1, 2),   # P1, P2 (subspecies, too short), P8 (synonym, Russia)
        "9": (1, 1, 0, 0, 1, 1),   # P3 (Canada)
        "12": (1, 1, 1, 1, 0, 1),  # P5 (own by institution)
    }
    evidence = dict(con.execute("SELECT taxon_id, record_count FROM evidence WHERE source = 'bold'").fetchall())
    assert evidence == {"7": 2, "12": 1}  # specimens from Europe, compliant or not
    assert con.execute("SELECT bold_snapshot FROM run").fetchone()[0] == "2026-05-22"
    assert con.execute("SELECT count(*) FROM specimen").fetchone()[0] == 8  # plant and COI-3P left out
    import pandas as pd
    review = pd.read_excel(workspace / "review" / "bold_names.xlsx", sheet_name="Names to review")
    row = review[review.original_name == "Aagaardia protenza"].iloc[0]
    assert (row.suggestion, row.specimens) == ("Aagaardia protensa", 2)
    return result


def test_tsv(workspace):
    (workspace / "bold" / "manual" / "BOLD_Public.22-May-2026.tsv").write_text(TSV)
    result = check_results(workspace, bold.import_bold(settings_with_own(), workspace / "g.duckdb"))
    assert "3 backbone species have at least one compliant barcode; 2 have one from a specimen collected in Europe" in result.message


def test_archive(workspace):
    with zipfile.ZipFile(workspace / "bold" / "manual" / "BOLD_Public.22-May-2026.zip", "w") as archive:
        archive.writestr("BOLD_Public.22-May-2026/BOLD_Public.22-May-2026.tsv", TSV)
        archive.writestr("BOLD_Public.22-May-2026/BOLD_Public.22-May-2026.fasta", ">P1\nACGT\n")
    check_results(workspace, bold.import_bold(settings_with_own(), workspace / "g.duckdb"))


def test_parquet(workspace, tmp_path):
    tsv = tmp_path / "x.tsv"
    tsv.write_text(TSV)
    target = workspace / "bold" / "manual" / "BOLD_Public.22-May-2026.parquet"
    duckdb.execute(f"COPY (SELECT * FROM read_csv('{tsv}', delim='\\t', all_varchar=true)) TO '{target}'")
    check_results(workspace, bold.import_bold(settings_with_own(), workspace / "g.duckdb"))


def test_no_own_lists(workspace):
    (workspace / "bold" / "manual" / "BOLD_Public.22-May-2026.tsv").write_text(TSV)
    settings = load_settings()
    settings.own_projects, settings.own_institutions = [], []
    result = bold.import_bold(settings, workspace / "g.duckdb")
    assert result.ok, result.message
    con = duckdb.connect(str(workspace / "g.duckdb"))
    assert con.execute("SELECT sum(own) FROM barcode_status").fetchone()[0] == 0


def test_missing_and_mismatched_snapshot(workspace):
    result = bold.import_bold(load_settings(), workspace / "g.duckdb")
    assert not result.ok and "No BOLD snapshot found" in result.message
    (workspace / "bold" / "manual" / "BOLD_Public.22-May-2026.tsv").write_text(TSV)
    settings = load_settings()
    settings.bold = {**settings.bold, "snapshot": "2026-06-30"}
    result = bold.import_bold(settings, workspace / "g.duckdb")
    assert not result.ok and "is from 2026-05-22" in result.message


def test_not_a_bold_file(workspace):
    (workspace / "bold" / "manual" / "something.tsv").write_text("a\tb\n1\t2\n")
    result = bold.import_bold(load_settings(), workspace / "g.duckdb")
    assert not result.ok and "lacks the BCDM column(s)" in result.message
