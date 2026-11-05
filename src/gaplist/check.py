"""Phase 0 check: are the settings valid and is the database ready?

Used by the first section of the notebook, and from the command line with
``pixi run check``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import db, paths
from .config import Settings, SettingsError, load_settings


@dataclass
class CheckResult:
    ok: bool
    message: str
    settings: Settings | None = None

    def __str__(self) -> str:
        status = "OK" if self.ok else "PROBLEM"
        return f"[{status}] {self.message}"


def run_check() -> CheckResult:
    try:
        settings = load_settings()
    except SettingsError as err:
        return CheckResult(False, str(err))

    con = db.connect()
    try:
        counts = db.table_counts(con)
    finally:
        con.close()

    filled = [name for name, n in counts.items() if n]
    db_line = (
        "The database is empty, ready for a first run."
        if not filled
        else "The database already holds results from an earlier run: "
        + ", ".join(f"{name} ({counts[name]:,} rows)" for name in filled)
        + "."
    )
    message = "\n".join(
        [
            "Settings are valid.",
            settings.summary(),
            f"Database: {paths.database_path()}",
            db_line,
        ]
    )
    return CheckResult(True, message, settings)


def main() -> None:
    result = run_check()
    print(result)
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
