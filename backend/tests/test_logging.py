from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import ActivityRepository, configure_logging, connect, init_db  # noqa: E402


class TestLogging(unittest.TestCase):
    def test_db_initialization_logs_info(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            configure_logging("INFO")
            with self.assertLogs("app.db", level="INFO") as captured:
                init_db(db_path=db_path)
            logs = "\n".join(captured.output)
            self.assertIn("Initializing database", logs)
            self.assertIn("Database initialization completed", logs)

    def test_repository_logs_debug_queries(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            configure_logging("DEBUG")
            with connect(db_path=db_path) as conn:
                repo = ActivityRepository(conn)
                with self.assertLogs("app.repositories.base", level="DEBUG") as captured:
                    repo.create_venue(
                        name="Central Library",
                        address="Square 1",
                        city="Amsterdam",
                    )
                logs = "\n".join(captured.output)
                self.assertIn("execute query=", logs)


if __name__ == "__main__":
    unittest.main()

