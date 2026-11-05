import io
import zipfile

import duckdb
import pytest

from gaplist import backbone, gbif, paths
from gaplist.config import load_settings

from .test_backbone import METADATA, NAME_USAGE

HEADER = "taxonKey\tscientificName\tnumberOfOccurrences\ttaxonRank\tkingdom\tphylum\tclass\torder\tfamily\tspecies\tspeciesKey\n"
MAIN = HEADER + (
    # joins to the backbone by key (species 7 = Aagaardia protensa)
    "7\tAagaardia protensa (Brundin, 1947)\t40\tSPECIES\tAnimalia\tArthropoda\tInsecta\tDiptera\tChironomidae\tAagaardia protensa\t7\n"
    # a subspecies row of the same species: summed
    "8\tAagaardia protensa minor\t2\tSUBSPECIES\tAnimalia\tArthropoda\tInsecta\tDiptera\tChironomidae\tAagaardia protensa\t7\n"
    # a key from an older CoL release: matched by name
    "OLD1\tAagaardia sivertseni\t5\tSPECIES\tAnimalia\tArthropoda\tInsecta\tDiptera\tChironomidae\tAagaardia sivertseni\tOLD1\n"
    # not in the backbone at all
    "ZZZ\tNusquam inventus\t1\tSPECIES\tAnimalia\tArthropoda\tInsecta\tDiptera\tChironomidae\tNusquam inventus\tZZZ\n"
    # genus-level record without a species key: ignored
    "6\tAagaardia\t3\tGENUS\tAnimalia\tArthropoda\tInsecta\tDiptera\tChironomidae\t\t\n"
)
ALIEN = HEADER + "OLD1\tAagaardia sivertseni\t1\tSPECIES\tAnimalia\tArthropoda\tInsecta\tDiptera\tChironomidae\tAagaardia sivertseni\tOLD1\n"


def zipped(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("0001.csv", text)
    return buffer.getvalue()


class FakeClient:
    def __init__(self, ready=True):
        self.ready = ready
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        return f"000{len(self.requests)}-alien" if "ESTABLISHMENT_MEANS" in str(request) else f"000{len(self.requests)}-main"

    def status(self, key):
        if not self.ready:
            return {"status": "RUNNING"}
        return {"status": "SUCCEEDED", "downloadLink": key, "doi": f"10.15468/dl.{key}"}

    def download(self, url, target):
        target.write_bytes(zipped(ALIEN if "alien" in url else MAIN))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda root=None: data)
    (data / "col" / "manual").mkdir(parents=True)
    with zipfile.ZipFile(data / "col" / "manual" / "t.zip", "w") as archive:
        archive.writestr("metadata.yaml", METADATA)
        archive.writestr("NameUsage.tsv", NAME_USAGE)
    settings = load_settings()
    assert backbone.build_backbone(settings, data / "g.duckdb").ok
    return data


def test_predicate_follows_settings():
    settings = load_settings()
    main = gbif.build_predicate(settings, ["N"])
    keys = {p.get("key") for p in main["predicates"]}
    assert {"COUNTRY", "TAXON_KEY", "OCCURRENCE_STATUS", "BASIS_OF_RECORD", "HAS_COORDINATE"} <= keys
    assert next(p for p in main["predicates"] if p.get("key") == "COUNTRY")["values"] == settings.europe
    # records without a degree of establishment must be kept, not dropped by the "not"
    either = next(p for p in main["predicates"] if p["type"] == "or")
    assert either["predicates"][0] == {"type": "isNull", "parameter": "DEGREE_OF_ESTABLISHMENT"}
    alien = gbif.build_predicate(settings, ["N"], alien_only=True)
    assert alien["predicates"][-1]["key"] == "ESTABLISHMENT_MEANS"
    request = gbif.build_request(settings, ["N"], False, "u", "e@x")
    assert request["format"] == "SPECIES_LIST" and request["checklistKey"] == settings.gbif["checklist_key"]


def test_missing_credentials_are_explained(tmp_path, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(paths, "repo_root", lambda: tmp_path)  # no .env there
    for name in ("GBIF_USER", "GBIF_PASSWORD", "GBIF_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    result = gbif.import_gbif(settings, tmp_path / "g.duckdb")
    assert not result.ok and "Copy .env.example to .env" in result.message


def test_waiting_then_resuming_reuses_downloads(workspace):
    client = FakeClient(ready=False)
    first = gbif.import_gbif(load_settings(), workspace / "g.duckdb", client=client)
    assert first.pending and "Run this cell again later" in first.message
    assert len(client.requests) == 2
    client.ready = True
    second = gbif.import_gbif(load_settings(), workspace / "g.duckdb", client=client)
    assert second.ok, second.message
    assert len(client.requests) == 2  # no new requests: the same downloads were picked up


def test_evidence(workspace):
    result = gbif.import_gbif(load_settings(), workspace / "g.duckdb", client=FakeClient())
    assert result.ok, result.message
    assert "1 matched to the backbone by key, 1 by name; 1 could not be placed" in result.message
    assert "https://doi.org/10.15468/dl.0001-main" in result.message
    con = duckdb.connect(str(workspace / "g.duckdb"))
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT taxon_id, record_count, possibly_alien FROM evidence WHERE source = 'gbif'").fetchall()}
    assert rows == {"7": (42, False), "9": (5, True)}
    outcomes = dict(con.execute("SELECT original_name, outcome FROM name_resolution WHERE source = 'gbif'").fetchall())
    assert outcomes == {"Aagaardia sivertseni": "exact", "Nusquam inventus": "unmatched"}
    assert con.execute("SELECT gbif_download_key, gbif_alien_download_key FROM run").fetchone() == (
        "0001-main", "0002-alien")
