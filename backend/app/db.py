from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "civiccircles.db"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "sql"
SCHEMA_PATH = SCHEMA_DIR / "001_initial_schema.sql"
logger = logging.getLogger(__name__)


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    logger.debug("Opening SQLite connection at %s", db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _resolve_schema_files(schema_path: Path | str | None) -> list[Path]:
    if schema_path is None:
        return sorted(SCHEMA_DIR.glob("*.sql"))
    path = Path(schema_path)
    if path.is_dir():
        return sorted(path.glob("*.sql"))
    return [path]


def init_db(
    db_path: Path | str = DEFAULT_DB_PATH,
    schema_path: Path | str | None = None,
) -> None:
    schema_files = _resolve_schema_files(schema_path)
    if not schema_files:
        raise FileNotFoundError(f"No schema files found for {schema_path or SCHEMA_DIR}")
    logger.info("Initializing database at %s with %d schema file(s)", db_path, len(schema_files))
    with connect(db_path) as conn:
        for file_path in schema_files:
            logger.info("Applying schema file %s", file_path.name)
            conn.executescript(file_path.read_text(encoding="utf-8"))
    logger.info("Database initialization completed for %s", db_path)
