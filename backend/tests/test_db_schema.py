from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import connect, init_db  # noqa: E402


class TestDatabaseSchema(unittest.TestCase):
    def test_schema_creates_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
                table_names = {row["name"] for row in rows}

        expected_tables = {
            "residents",
            "activities",
            "circles",
            "invitations",
            "matching_runs",
            "match_candidates",
            "resident_activity_similarity",
            "peer_ratings",
            "peer_rating_rollups",
            "audit_events",
        }
        for table in expected_tables:
            self.assertIn(table, table_names)

    def test_foreign_keys_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                row = conn.execute("PRAGMA foreign_keys;").fetchone()
                self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()

