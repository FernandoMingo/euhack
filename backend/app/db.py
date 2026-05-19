from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "civiccircles.db"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "sql"
SCHEMA_PATH = SCHEMA_DIR / "001_initial_schema.sql"
logger = logging.getLogger(__name__)

_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS _schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    logger.debug("Opening SQLite connection at %s", db_path)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _resolve_schema_files(schema_path: Path | str | None) -> list[Path]:
    """
    Returns the migration files to apply, in order.

    - `None`  -> every `*.sql` in `SCHEMA_DIR`.
    - dir     -> every `*.sql` in that directory.
    - file    -> just that file (legacy single-script behavior).
    """
    if schema_path is None:
        return sorted(SCHEMA_DIR.glob("*.sql"))
    path = Path(schema_path)
    if path.is_dir():
        return sorted(path.glob("*.sql"))
    return [path]


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    conn.executescript(_MIGRATIONS_TABLE_SQL)
    rows = conn.execute("SELECT name FROM _schema_migrations").fetchall()
    return {row["name"] for row in rows}


def _alias_renamed_migration(
    conn: sqlite3.Connection,
    applied: set[str],
    *,
    old_name: str,
    new_name: str,
) -> None:
    """Record a renamed migration so existing databases skip re-applying it."""
    if old_name in applied and new_name not in applied:
        conn.execute(
            "INSERT INTO _schema_migrations (name, applied_at) VALUES (?, ?)",
            (new_name, datetime.now(timezone.utc).isoformat()),
        )
        applied.add(new_name)


def init_db(
    db_path: Path | str = DEFAULT_DB_PATH,
    schema_path: Path | str | None = None,
) -> None:
    """
    Initialize the SQLite database by running migration scripts in order.

    Applied migrations are recorded in `_schema_migrations` so re-running
    this function on an existing database only applies new scripts. Each
    migration is run inside a transaction so a failing script does not
    leave the database half-migrated.

    `schema_path` can be a single SQL file (legacy callers), a directory
    of `*.sql` migration files, or `None` (uses the default `sql/` dir).
    """
    schema_files = _resolve_schema_files(schema_path)
    if not schema_files:
        raise FileNotFoundError(f"No schema files found for {schema_path or SCHEMA_DIR}")

    logger.info(
        "Initializing database at %s with %d migration file(s)",
        db_path,
        len(schema_files),
    )
    with connect(db_path) as conn:
        applied = _applied_migrations(conn)
        _alias_renamed_migration(
            conn,
            applied,
            old_name="003_onboarding_fields.sql",
            new_name="003a_onboarding_fields.sql",
        )
        for file_path in schema_files:
            if file_path.name in applied:
                logger.debug("Skipping already-applied migration %s", file_path.name)
                continue
            logger.info("Applying migration %s", file_path.name)
            conn.executescript(file_path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO _schema_migrations (name, applied_at) VALUES (?, ?)",
                (file_path.name, datetime.now(timezone.utc).isoformat()),
            )
    logger.info("Database initialization completed for %s", db_path)
