import shutil
from pathlib import Path

import pytest

from gaplist import paths
from gaplist.config import SettingsError, load_settings


@pytest.fixture
def config_copy(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(paths.config_dir(), target)
    return target


def test_shipped_settings_are_valid():
    settings = load_settings()
    assert "NL" in settings.europe
    assert "NO" in settings.europe  # YAML must not read Norway as "false"
    assert "RU" not in settings.europe
    assert "AZ" not in settings.europe
    assert {"AM", "GE", "TR"} <= set(settings.europe)
    assert settings.bold["markers"] == ["COI-5P"]
    assert settings.bold["min_length"] == 500
    assert settings.col["kingdoms"] == ["Animalia"]
    assert len(settings.fingerprint) == 12


def test_bad_country_code_is_reported_plainly(config_copy: Path):
    path = config_copy / "europe.yaml"
    path.write_text(path.read_text() + "  - nl  # lower case\n  - NL\n")
    with pytest.raises(SettingsError) as err:
        load_settings(config_copy)
    text = str(err.value)
    assert "'nl' is not a two-letter country code" in text
    assert "NL is listed twice" in text


def test_all_problems_reported_together(config_copy: Path):
    sources = config_copy / "sources.yaml"
    sources.write_text(sources.read_text().replace("min_length: 500", "min_length: lots"))
    curation = config_copy / "curation.tsv"
    curation.write_text(curation.read_text() + "legacy\tAus bus\tmaybe\t\tRV\t2026-11-05\t\n")
    with pytest.raises(SettingsError) as err:
        load_settings(config_copy)
    assert len(err.value.problems) == 2


def test_broken_yaml_names_the_file(config_copy: Path):
    (config_copy / "own_barcodes.yaml").write_text("projects: [unclosed\n")
    with pytest.raises(SettingsError) as err:
        load_settings(config_copy)
    assert "own_barcodes.yaml cannot be read" in str(err.value)


def test_fingerprint_changes_with_settings(config_copy: Path):
    before = load_settings(config_copy).fingerprint
    path = config_copy / "europe.yaml"
    path.write_text(path.read_text().replace("  - SJ", "  # - SJ"))
    assert load_settings(config_copy).fingerprint != before
