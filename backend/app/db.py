from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "civiccircles.db"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "001_initial_schema.sql"
logger = logging.getLogger(__name__)


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    logger.debug("Opening SQLite connection at %s", db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH, schema_path: Path | str = SCHEMA_PATH) -> None:
    logger.info("Initializing database at %s using schema %s", db_path, schema_path)
    schema_sql = Path(schema_path).read_text(encoding="utf-8")
    with connect(db_path) as conn:
        conn.executescript(schema_sql)
    logger.info("Database initialization completed for %s", db_path)

