from __future__ import annotations

import argparse
from pathlib import Path

from app.db import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize CivicCircles SQLite database.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(__file__).resolve().parent / "civiccircles.db",
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=Path(__file__).resolve().parent / "sql",
        help="Path to a SQL schema file or directory of migration files.",
    )
    args = parser.parse_args()
    init_db(db_path=args.db_path, schema_path=args.schema_path)
    print(f"Initialized database at {args.db_path}")


if __name__ == "__main__":
    main()
