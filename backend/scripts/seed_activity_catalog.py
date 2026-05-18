from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import configure_logging, connect, init_db  # noqa: E402
from app.seed import DEFAULT_CATALOG_PATH, seed_activity_templates  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the activity templates catalog into SQLite.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=REPO_ROOT / "civiccircles.db",
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--catalog-path",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="Path to the activity catalog JSON file.",
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip database initialization. Use only if the database already has the schema applied.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING).",
    )
    args = parser.parse_args()

    configure_logging(args.log_level)

    if not args.skip_init:
        init_db(db_path=args.db_path)

    with connect(db_path=args.db_path) as conn:
        count = seed_activity_templates(conn=conn, catalog_path=args.catalog_path)
    print(f"Seeded activity catalog. Total templates in database: {count}")


if __name__ == "__main__":
    main()
