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
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _discover_migrations(schema_dir: Path) -> list[Path]:
    return sorted(p for p in schema_dir.glob("*.sql"))


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    conn.executescript(_MIGRATIONS_TABLE_SQL)
    rows = conn.execute("SELECT name FROM _schema_migrations").fetchall()
    return {row["name"] for row in rows}


def init_db(
    db_path: Path | str = DEFAULT_DB_PATH,
    schema_path: Path | str | None = None,
    schema_dir: Path | str | None = None,
) -> None:
    """
    Initialize the SQLite database by running pending migration scripts in order.

    Applied migrations are recorded in `_schema_migrations`, so re-running this
    function on an existing database only applies new scripts.

    If `schema_path` is given, that single script is executed regardless of
    migration history (legacy behavior preserved for callers that pass it).
    Otherwise every `*.sql` file in `schema_dir` (default: backend/sql) that
    hasn't been applied yet is run in lexicographic order.
    """
    if schema_path is not None:
        logger.info("Initializing database at %s using schema %s", db_path, schema_path)
        schema_sql = Path(schema_path).read_text(encoding="utf-8")
        with connect(db_path) as conn:
            conn.executescript(schema_sql)
        logger.info("Database initialization completed for %s", db_path)
        return

    resolved_dir = Path(schema_dir) if schema_dir is not None else SCHEMA_DIR
    migrations = _discover_migrations(resolved_dir)
    if not migrations:
        raise FileNotFoundError(f"No migration scripts found in {resolved_dir}")

    logger.info(
        "Initializing database at %s using migrations from %s",
        db_path,
        resolved_dir,
    )
    with connect(db_path) as conn:
        applied = _applied_migrations(conn)
        for migration in migrations:
            if migration.name in applied:
                logger.debug("Skipping already-applied migration %s", migration.name)
                continue
            logger.info("Applying migration %s", migration.name)
            conn.executescript(migration.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO _schema_migrations (name, applied_at) VALUES (?, ?)",
                (migration.name, datetime.now(timezone.utc).isoformat()),
            )
    logger.info("Database initialization completed for %s", db_path)
