from gaplist import db
from gaplist.config import load_settings


def test_schema_creates_all_tables(tmp_path):
    con = db.connect(tmp_path / "test.duckdb")
    assert db.table_counts(con) == {t: 0 for t in db.TABLES}


def test_connect_twice_is_harmless(tmp_path):
    path = tmp_path / "test.duckdb"
    db.connect(path).close()
    con = db.connect(path)
    assert set(db.table_counts(con)) == set(db.TABLES)


def test_runs_are_numbered(tmp_path):
    con = db.connect(tmp_path / "test.duckdb")
    settings = load_settings()
    assert db.start_run(con, settings) == 1
    assert db.start_run(con, settings) == 2
    fingerprint = con.execute("SELECT settings_fingerprint FROM run WHERE run_id = 2").fetchone()[0]
    assert fingerprint == settings.fingerprint
