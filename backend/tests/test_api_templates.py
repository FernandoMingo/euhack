from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import connect  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.repositories import ActivityTemplateRepository  # noqa: E402


class TemplatesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "test.db"
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

        # Seed two templates directly through the repo for an isolated test fixture.
        with connect(self.db_path) as conn:
            repo = ActivityTemplateRepository(conn)
            t1 = repo.upsert_template(
                code="photo-walk",
                title="Photography Walk",
                description="A calm walk with cameras.",
                family="photography",
                typical_duration_minutes=90,
                typical_group_size_min=3,
                typical_group_size_max=6,
                typical_cost_band="free",
                social_energy="low",
                setting="outdoor",
                intensity="light",
                noise_level="quiet",
                structure="self_paced",
                risk_level="low",
            )
            repo.replace_tags(template_id=t1.id, tags=["theme:outdoor", "skill:beginner_friendly"])
            t2 = repo.upsert_template(
                code="board-games",
                title="Board Game Evening",
                description="Casual board games at the library.",
                family="tabletop_games",
                typical_duration_minutes=120,
                typical_group_size_min=4,
                typical_group_size_max=8,
                typical_cost_band="free",
                social_energy="medium",
                setting="indoor",
                intensity="still",
                noise_level="moderate",
                structure="self_paced",
                risk_level="low",
            )
            repo.replace_tags(template_id=t2.id, tags=["attribute:social"])
            conn.commit()

    def test_list_templates(self) -> None:
        r = self.client.get("/api/templates")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body), 2)

    def test_list_templates_filtered_by_family(self) -> None:
        r = self.client.get("/api/templates?family=photography")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["code"], "photo-walk")

    def test_list_families(self) -> None:
        r = self.client.get("/api/templates/families")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sorted(r.json()), ["photography", "tabletop_games"])

    def test_search_by_tag(self) -> None:
        r = self.client.get("/api/templates/by-tag/theme:outdoor")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["code"], "photo-walk")

    def test_get_template_by_code(self) -> None:
        r = self.client.get("/api/templates/photo-walk")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["family"], "photography")
        self.assertIn("theme:outdoor", body["tags"])

    def test_get_template_404(self) -> None:
        r = self.client.get("/api/templates/no-such-template")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
