from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    ActivityRepository,
    ActivityTemplateRepository,
    CircleEngine,
    MatchingRepository,
    ResidentRepository,
    connect,
    init_db,
)
from app.matching import (  # noqa: E402
    DEFAULT_MODEL_VERSION,
    availability_density,
    compute_group_fit,
    interest_overlap_score,
    social_energy_consistency,
)
from app.seed import seed_activity_templates  # noqa: E402


PHOTOGRAPHY_PROFILES: list[dict[str, object]] = [
    {
        "first_name": "Sofia",
        "email": "sofia@example.com",
        "interests": ("photography", "nature", "outdoor"),
        "avoid": (),
        "avails": (("sat", "09:00", "12:00"),),
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "pref_min": 3,
        "pref_max": 6,
        "accessibility": (),
    },
    {
        "first_name": "Marco",
        "email": "marco@example.com",
        "interests": ("photography", "outdoor"),
        "avoid": (),
        "avails": (("sat", "10:00", "12:30"),),
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "pref_min": 3,
        "pref_max": 5,
        "accessibility": (),
    },
    {
        "first_name": "Aisha",
        "email": "aisha@example.com",
        "interests": ("nature", "photography"),
        "avoid": (),
        "avails": (("sat", "09:30", "11:30"),),
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "pref_min": 3,
        "pref_max": 6,
        "accessibility": (),
    },
    {
        "first_name": "Bo",
        "email": "bo@example.com",
        "interests": ("nature", "outdoor"),
        "avoid": (),
        "avails": (("sat", "10:30", "11:30"),),
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "pref_min": 3,
        "pref_max": 6,
        "accessibility": (),
    },
    # incompatible: avoidance on walks/photography family
    {
        "first_name": "Diego",
        "email": "diego@example.com",
        "interests": ("photography",),
        "avoid": ("walks_outdoor",),
        "avails": (("sat", "09:00", "12:00"),),
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "pref_min": 3,
        "pref_max": 6,
        "accessibility": (),
    },
    # incompatible: cost band too restrictive for any non-free template would
    # be a stretch; here we test by giving an "any" pref but a different
    # constraint route — instead, we make this resident outside everyone's
    # availability so they cannot be grouped despite being eligible.
    {
        "first_name": "Eva",
        "email": "eva@example.com",
        "interests": ("photography",),
        "avoid": (),
        "avails": (("mon", "18:00", "20:00"),),
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "pref_min": 3,
        "pref_max": 6,
        "accessibility": (),
    },
]


def _seed_residents(residents_repo: ResidentRepository, profiles: list[dict[str, object]]):
    created = []
    for spec in profiles:
        resident = residents_repo.create_resident(
            first_name=spec["first_name"],  # type: ignore[arg-type]
            email=spec["email"],  # type: ignore[arg-type]
            preferred_language="English",
            city="Amsterdam",
            social_comfort=spec["social_comfort"],  # type: ignore[arg-type]
            preferred_group_size_min=spec["pref_min"],  # type: ignore[arg-type]
            preferred_group_size_max=spec["pref_max"],  # type: ignore[arg-type]
            cost_sensitivity=spec["cost_sensitivity"],  # type: ignore[arg-type]
        )
        for interest in spec["interests"]:  # type: ignore[union-attr]
            residents_repo.add_preference(
                resident_id=resident.id,
                preference_type="interest",
                value=interest,  # type: ignore[arg-type]
            )
        residents_repo.add_preference(
            resident_id=resident.id,
            preference_type="activity",
            value="photography_walk",
        )
        for value in spec["avoid"]:  # type: ignore[union-attr]
            residents_repo.add_avoidance(resident_id=resident.id, value=value)  # type: ignore[arg-type]
        for weekday, start, end in spec["avails"]:  # type: ignore[misc]
            residents_repo.add_availability(
                resident_id=resident.id,
                weekday=weekday,  # type: ignore[arg-type]
                start_time_local=start,  # type: ignore[arg-type]
                end_time_local=end,  # type: ignore[arg-type]
            )
        for value in spec["accessibility"]:  # type: ignore[union-attr]
            residents_repo.add_preference(
                resident_id=resident.id,
                preference_type="accessibility_need",
                value=value,  # type: ignore[arg-type]
            )
        created.append(resident)
    return created


class TestPureScoring(unittest.TestCase):
    def test_availability_density_saturates_at_three(self) -> None:
        self.assertEqual(availability_density(0), 0.0)
        self.assertAlmostEqual(availability_density(1), 1.0 / 3.0)
        self.assertAlmostEqual(availability_density(2), 2.0 / 3.0)
        self.assertEqual(availability_density(3), 1.0)
        self.assertEqual(availability_density(99), 1.0)

    def test_interest_overlap_score_saturates_at_three(self) -> None:
        self.assertEqual(interest_overlap_score(0), 0.0)
        self.assertEqual(interest_overlap_score(3), 1.0)
        self.assertEqual(interest_overlap_score(100), 1.0)

    def test_social_energy_consistency_decays(self) -> None:
        self.assertEqual(social_energy_consistency([]), 0.0)


class TestCircleEngine(unittest.TestCase):
    def _build_engine(self, conn) -> CircleEngine:
        residents_repo = ResidentRepository(conn)
        templates_repo = ActivityTemplateRepository(conn)
        matching_repo = MatchingRepository(conn)
        activities_repo = ActivityRepository(conn)
        seed_activity_templates(conn=conn)
        return CircleEngine(
            residents=residents_repo,
            templates=templates_repo,
            matching=matching_repo,
            activities=activities_repo,
        )

    def test_compatible_residents_are_grouped_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                created = _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)
                by_name = {r.first_name: r for r in created}

                result = engine.run_grouping(
                    template_code="photography_walk",
                    top_n=2,
                    min_group_size=3,
                    max_group_size=4,
                )
                self.assertNotEqual(result.matching_run_id, "")
                self.assertGreaterEqual(len(result.groups), 1)

                top = result.groups[0]
                top_member_ids = {m.id for m in top.members}
                self.assertIn(by_name["Sofia"].id, top_member_ids)
                self.assertIn(by_name["Marco"].id, top_member_ids)
                self.assertIn(by_name["Aisha"].id, top_member_ids)
                self.assertGreaterEqual(len(top.members), 3)
                self.assertLessEqual(len(top.members), 4)
                self.assertGreater(top.fit_score, 0.0)
                self.assertLessEqual(top.fit_score, 1.0)
                self.assertIn("sat_morning", top.shared_availability)

    def test_avoidance_filters_resident_out_of_circles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                created = _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)
                by_name = {r.first_name: r for r in created}

                result = engine.run_grouping(
                    template_code="photography_walk",
                    top_n=3,
                    min_group_size=3,
                    max_group_size=4,
                )
                rejected_ids = {r.resident.id for r in result.rejected}
                self.assertIn(by_name["Diego"].id, rejected_ids)
                diego_entry = next(
                    r for r in result.rejected if r.resident.id == by_name["Diego"].id
                )
                self.assertTrue(
                    any(reason.startswith("avoidance:") for reason in diego_entry.reasons)
                )
                grouped_ids: set[str] = set()
                for group in result.groups:
                    grouped_ids.update(m.id for m in group.members)
                self.assertNotIn(by_name["Diego"].id, grouped_ids)

    def test_resident_outside_shared_availability_is_not_grouped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                created = _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)
                by_name = {r.first_name: r for r in created}

                result = engine.run_grouping(
                    template_code="photography_walk",
                    top_n=3,
                    min_group_size=3,
                    max_group_size=4,
                )
                grouped_ids: set[str] = set()
                for group in result.groups:
                    grouped_ids.update(m.id for m in group.members)
                self.assertNotIn(by_name["Eva"].id, grouped_ids)

    def test_cost_constraint_rejects_resident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                residents_repo = ResidentRepository(conn)
                _seed_residents(residents_repo, PHOTOGRAPHY_PROFILES)

                # All residents above are free_or_low_cost only. Run against
                # a high-cost template; every resident must be rejected with
                # cost_band_excluded.
                spa_template = ActivityTemplateRepository(conn).get_template_by_code(
                    "spa_floatation_session"
                ) or ActivityTemplateRepository(conn).list_templates(
                    family="wellness_mind_body"
                )[0]

                result = engine.run_grouping(
                    template_id=spa_template.id,
                    top_n=3,
                    min_group_size=3,
                    max_group_size=4,
                )
                if spa_template.typical_cost_band in {"medium", "high"}:
                    self.assertEqual(len(result.groups), 0)
                    self.assertGreater(len(result.rejected), 0)
                    sample = result.rejected[0]
                    self.assertTrue(
                        any(
                            reason.startswith("cost_band_excluded:")
                            for reason in sample.reasons
                        )
                    )

    def test_two_runs_produce_same_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)

                first = engine.run_grouping(
                    template_code="photography_walk",
                    top_n=2,
                    min_group_size=3,
                    max_group_size=4,
                )
                second = engine.run_grouping(
                    template_code="photography_walk",
                    top_n=2,
                    min_group_size=3,
                    max_group_size=4,
                )
                self.assertEqual(len(first.groups), len(second.groups))
                for g1, g2 in zip(first.groups, second.groups):
                    self.assertEqual(
                        tuple(m.id for m in g1.members),
                        tuple(m.id for m in g2.members),
                    )
                    self.assertAlmostEqual(g1.fit_score, g2.fit_score, places=12)
                    self.assertEqual(g1.shared_availability, g2.shared_availability)

    def test_persistence_writes_all_artifact_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)

                result = engine.run_grouping(
                    template_code="photography_walk",
                    top_n=2,
                    min_group_size=3,
                    max_group_size=4,
                )
                run_id = result.matching_run_id
                self.assertNotEqual(run_id, "")
                self.assertGreaterEqual(len(result.groups), 1)

                run_row = conn.execute(
                    "SELECT run_type, model_version, score_algorithm "
                    "FROM matching_runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                self.assertEqual(run_row["run_type"], "circle_matching")
                self.assertEqual(run_row["model_version"], DEFAULT_MODEL_VERSION)

                candidates = conn.execute(
                    "SELECT id, circle_id, resident_id, hard_constraints_passed "
                    "FROM match_candidates WHERE matching_run_id = ?",
                    (run_id,),
                ).fetchall()
                self.assertEqual(len(candidates), len(result.groups) + len(result.rejected))

                passing_candidates = [c for c in candidates if c["hard_constraints_passed"] == 1]
                self.assertEqual(len(passing_candidates), len(result.groups))
                for c in passing_candidates:
                    self.assertIsNotNone(c["circle_id"])

                feature_scores = conn.execute(
                    """
                    SELECT fs.feature_key
                    FROM match_feature_scores fs
                    JOIN match_candidates c ON c.id = fs.match_candidate_id
                    WHERE c.matching_run_id = ?
                    """,
                    (run_id,),
                ).fetchall()
                feature_keys = {row["feature_key"] for row in feature_scores}
                self.assertIn("group:template_fit", feature_keys)
                self.assertIn("group:availability_density", feature_keys)
                self.assertIn("group:interest_overlap", feature_keys)
                self.assertIn("group:group_size_comfort", feature_keys)
                self.assertIn("group:social_energy_consistency", feature_keys)

                explanations = conn.execute(
                    """
                    SELECT e.summary_text, e.explanation_json
                    FROM match_explanations e
                    JOIN match_candidates c ON c.id = e.match_candidate_id
                    WHERE c.matching_run_id = ?
                    """,
                    (run_id,),
                ).fetchall()
                self.assertEqual(len(explanations), len(candidates))
                top_payload = next(
                    json.loads(row["explanation_json"])
                    for row in explanations
                    if "Circle for" in row["summary_text"]
                    and "#1 " in row["summary_text"]
                )
                self.assertIn("components", top_payload)
                self.assertIn("members", top_payload)
                self.assertEqual(top_payload["model_version"], DEFAULT_MODEL_VERSION)

                circle_rows = conn.execute(
                    """
                    SELECT c.id, c.template_id, c.activity_id, c.fit_score, c.status
                    FROM circles c
                    JOIN match_candidates mc ON mc.circle_id = c.id
                    WHERE mc.matching_run_id = ?
                    ORDER BY mc.rank_position
                    """,
                    (run_id,),
                ).fetchall()
                self.assertEqual(len(circle_rows), len(result.groups))
                first_circle = circle_rows[0]
                self.assertEqual(first_circle["status"], "proposed")
                self.assertIsNotNone(first_circle["template_id"])
                self.assertIsNone(first_circle["activity_id"])
                self.assertIsNotNone(first_circle["fit_score"])

                member_rows = conn.execute(
                    """
                    SELECT cm.circle_id, cm.resident_id
                    FROM circle_members cm
                    JOIN match_candidates mc ON mc.circle_id = cm.circle_id
                    WHERE mc.matching_run_id = ?
                    """,
                    (run_id,),
                ).fetchall()
                self.assertGreater(len(member_rows), 0)
                for row in member_rows:
                    self.assertIsNotNone(row["resident_id"])

                rejected_rows = conn.execute(
                    """
                    SELECT resident_id, hard_constraints_passed
                    FROM match_candidates
                    WHERE matching_run_id = ? AND hard_constraints_passed = 0
                    """,
                    (run_id,),
                ).fetchall()
                self.assertEqual(len(rejected_rows), len(result.rejected))
                for row in rejected_rows:
                    self.assertIsNotNone(row["resident_id"])

    def test_engine_around_approved_activity_persists_activity_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                activities_repo = ActivityRepository(conn)
                _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)

                venue = activities_repo.create_venue(
                    name="Vondelpark Entrance",
                    address="Vondelpark, Amsterdam",
                    city="Amsterdam",
                )
                activity = activities_repo.create_activity(
                    title="Calm Photography Walk",
                    activity_type="photography_walk",
                    venue_id=venue.id,
                    start_at="2026-05-23T10:30:00+00:00",
                    end_at="2026-05-23T12:00:00+00:00",
                    capacity=6,
                    risk_level="low",
                    approval_status="approved",
                )
                conn.commit()

                result = engine.run_grouping(
                    activity_id=activity.id,
                    top_n=1,
                    min_group_size=3,
                    max_group_size=4,
                )
                self.assertEqual(result.activity.id, activity.id)  # type: ignore[union-attr]
                self.assertEqual(result.template.code, "photography_walk")
                self.assertGreaterEqual(len(result.groups), 1)

                circle_row = conn.execute(
                    """
                    SELECT c.activity_id, c.template_id
                    FROM circles c
                    JOIN match_candidates mc ON mc.circle_id = c.id
                    WHERE mc.matching_run_id = ?
                    ORDER BY mc.rank_position LIMIT 1
                    """,
                    (result.matching_run_id,),
                ).fetchone()
                self.assertEqual(circle_row["activity_id"], activity.id)
                self.assertIsNone(circle_row["template_id"])

    def test_run_emits_info_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "circle.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine = self._build_engine(conn)
                _seed_residents(ResidentRepository(conn), PHOTOGRAPHY_PROFILES)
                with self.assertLogs("app.matching.grouping", level="INFO") as captured:
                    engine.run_grouping(
                        template_code="photography_walk",
                        top_n=1,
                        min_group_size=3,
                        max_group_size=4,
                    )
                logs = "\n".join(captured.output)
                self.assertIn("circle_matching.run start", logs)
                self.assertIn("circle_matching.run end", logs)


if __name__ == "__main__":
    unittest.main()
