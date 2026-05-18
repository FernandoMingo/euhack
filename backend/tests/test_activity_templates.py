from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import ActivityTemplateRepository, connect, init_db  # noqa: E402
from app.seed import DEFAULT_CATALOG_PATH, load_activity_catalog, seed_activity_templates  # noqa: E402


REQUIRED_FIELDS = {
    "code",
    "title",
    "description",
    "family",
    "typical_duration_minutes",
    "typical_group_size_min",
    "typical_group_size_max",
    "typical_cost_band",
    "social_energy",
    "setting",
    "intensity",
    "noise_level",
    "structure",
    "risk_level",
    "tags",
}

ALLOWED_COST = {"free", "low", "medium", "high"}
ALLOWED_ENERGY = {"low", "medium", "high"}
ALLOWED_SETTING = {"indoor", "outdoor", "mixed"}
ALLOWED_INTENSITY = {"still", "light", "active", "vigorous"}
ALLOWED_NOISE = {"quiet", "moderate", "loud"}
ALLOWED_STRUCTURE = {"guided", "self_paced", "mixed"}
ALLOWED_RISK = {"low", "medium", "high"}


class TestActivityCatalogIntegrity(unittest.TestCase):
    def test_catalog_is_well_formed(self) -> None:
        catalog = load_activity_catalog()
        self.assertGreater(len(catalog), 50, "Catalog should be reasonably large")

        codes = set()
        for entry in catalog:
            self.assertTrue(REQUIRED_FIELDS.issubset(entry.keys()))
            self.assertNotIn(entry["code"], codes, f"Duplicate code: {entry['code']}")
            codes.add(entry["code"])

            self.assertIn(entry["typical_cost_band"], ALLOWED_COST)
            self.assertIn(entry["social_energy"], ALLOWED_ENERGY)
            self.assertIn(entry["setting"], ALLOWED_SETTING)
            self.assertIn(entry["intensity"], ALLOWED_INTENSITY)
            self.assertIn(entry["noise_level"], ALLOWED_NOISE)
            self.assertIn(entry["structure"], ALLOWED_STRUCTURE)
            self.assertIn(entry["risk_level"], ALLOWED_RISK)
            self.assertGreater(int(entry["typical_duration_minutes"]), 0)
            self.assertGreaterEqual(int(entry["typical_group_size_min"]), 1)
            self.assertGreaterEqual(
                int(entry["typical_group_size_max"]),
                int(entry["typical_group_size_min"]),
            )

            tags = entry["tags"]
            self.assertIsInstance(tags, list)
            self.assertGreater(len(tags), 0)


class TestSeedActivityTemplates(unittest.TestCase):
    def test_seed_inserts_full_catalog(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                count = seed_activity_templates(conn=conn)
                self.assertGreater(count, 50)

                repo = ActivityTemplateRepository(conn)
                families = repo.list_families()
                self.assertIn("walks_outdoor", families)
                self.assertIn("food_drink", families)
                self.assertIn("arts_crafts", families)
                self.assertIn("videogames", families)

                pottery = repo.get_template_by_code("pottery_making_class")
                self.assertIsNotNone(pottery)
                assert pottery is not None
                tags = repo.get_tags(pottery.id)
                self.assertIn("attribute:creative", tags)

    def test_seed_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                first_count = seed_activity_templates(conn=conn)
                second_count = seed_activity_templates(conn=conn)
                self.assertEqual(first_count, second_count)


class TestSeedFromTempCatalog(unittest.TestCase):
    def test_seed_from_temporary_file(self) -> None:
        sample = [
            {
                "code": "test_activity",
                "title": "Test Activity",
                "description": "Test description.",
                "family": "test_family",
                "typical_duration_minutes": 60,
                "typical_group_size_min": 2,
                "typical_group_size_max": 6,
                "typical_cost_band": "free",
                "social_energy": "low",
                "setting": "indoor",
                "intensity": "still",
                "noise_level": "quiet",
                "structure": "self_paced",
                "risk_level": "low",
                "tags": ["attribute:test"],
            }
        ]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            catalog_path = Path(tmp_dir) / "catalog.json"
            catalog_path.write_text(json.dumps(sample), encoding="utf-8")
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                count = seed_activity_templates(conn=conn, catalog_path=catalog_path)
                self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
