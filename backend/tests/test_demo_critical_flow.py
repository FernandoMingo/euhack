from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402
from seed_demo import seed  # noqa: E402


class DemoCriticalFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "demo.db"
        self.app = create_app(db_path=self.db_path)
        seed(self.db_path)
        self.client = TestClient(self.app)

    def test_resident_invitations_include_all_seeded_activity_markers(self) -> None:
        response = self.client.get("/api/resident/invitations")
        self.assertEqual(response.status_code, 200, response.text)
        invitations = response.json()
        titles = {item["activity"]["title"] for item in invitations}
        self.assertGreaterEqual(len(invitations), 4)
        self.assertTrue(
            {
                "Calm Photography Walk",
                "Quiet Museum Morning",
                "Evening Board Games",
                "Slow Coffee & Sketching",
            }.issubset(titles)
        )
        for invitation in invitations:
            location = invitation["activity"]["location"]
            self.assertIsInstance(location["lat"], (int, float))
            self.assertIsInstance(location["lng"], (int, float))

    def test_nearby_demo_activity_is_created_once_and_not_moved(self) -> None:
        first = self.client.post("/api/demo/nearby-activity", json={"lat": 51.9225, "lng": 4.47917})
        self.assertEqual(first.status_code, 200, first.text)
        first_location = first.json()["activity"]["location"]
        self.assertAlmostEqual(first_location["lat"], 51.9225)
        self.assertAlmostEqual(first_location["lng"], 4.47917)

        second = self.client.post("/api/demo/nearby-activity", json={"lat": 52.0, "lng": 5.0})
        self.assertEqual(second.status_code, 200, second.text)
        second_location = second.json()["activity"]["location"]
        self.assertAlmostEqual(second_location["lat"], 51.9225)
        self.assertAlmostEqual(second_location["lng"], 4.47917)

    def test_catalog_preferences_are_non_empty(self) -> None:
        response = self.client.get("/api/catalog/preferences")
        self.assertEqual(response.status_code, 200, response.text)
        catalog = response.json()
        self.assertIn("photography_walk", {item["value"] for item in catalog["activity_types"]})
        self.assertGreater(len(catalog["interests"]), 0)
        self.assertGreater(len(catalog["accessibility_needs"]), 0)

    def test_patch_preferences_persists_and_keeps_locked_fields_locked(self) -> None:
        response = self.client.patch(
            "/api/residents/sofia-001/preferences",
            json={
                "preferences": {
                    "first_name": "HackedName",
                    "interests": ["theme:outdoor", "attribute:calm"],
                    "activity_preferences": ["photography_walk"],
                    "accessibility_needs": ["step_free_route"],
                    "avoid": ["alcohol"],
                    "availability": ["sat_morning"],
                    "social_comfort": "small_group_low_pressure",
                    "cost_sensitivity": "free_or_low_cost",
                    "preferred_group_size": {"min": 2, "max": 5},
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["saved"])

        profile = self.client.get("/api/resident/me")
        self.assertEqual(profile.status_code, 200, profile.text)
        resident = profile.json()
        self.assertEqual(resident["first_name"], "Sofia")
        self.assertCountEqual(resident["interests"], ["theme:outdoor", "attribute:calm"])
        self.assertEqual(resident["activity_preferences"], ["photography_walk"])
        self.assertEqual(resident["accessibility_needs"], ["step_free_route"])
        self.assertEqual(resident["avoid"], ["alcohol"])
        self.assertEqual(resident["availability"], ["sat_morning"])
        self.assertEqual(resident["preferred_group_size"]["min"], 2)
        self.assertEqual(resident["preferred_group_size"]["max"], 5)


if __name__ == "__main__":
    unittest.main()
