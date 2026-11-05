"""Where things live on disk.

Everything is relative to the repository root, so the pipeline works the
same wherever the repository is checked out.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Return the repository root (the folder that holds ``pyproject.toml``)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "config").is_dir():
            return parent
    # Installed outside a checkout: fall back to the working directory.
    return Path.cwd()


def config_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "config"


def data_dir(root: Path | None = None) -> Path:
    """Downloaded inputs and run outputs. Never committed to Git."""
    path = (root or repo_root()) / "data"
    path.mkdir(exist_ok=True)
    return path


def database_path(root: Path | None = None) -> Path:
    return data_dir(root) / "gaplist.duckdb"
