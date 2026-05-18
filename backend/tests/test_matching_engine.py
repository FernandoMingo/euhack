from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    ActivityTemplateRepository,
    MatchingRepository,
    ResidentRepository,
    connect,
    init_db,
)
from app.dataclasses import (  # noqa: E402
    ActivityTemplate,
    Resident,
    ResidentAvailability,
    ResidentAvoidance,
    ResidentPreference,
)
from app.matching import (  # noqa: E402
    AVOIDANCE_WEIGHT,
    DEFAULT_MODEL_VERSION,
    MatchingEngine,
    build_resident_vector,
    build_template_vector,
    check_template_constraints,
    cosine_similarity,
    weighted_total,
)
from app.seed import seed_activity_templates  # noqa: E402


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _resident(
    *,
    resident_id: str = "resident_test",
    social_comfort: str = "small_group_low_pressure",
    cost_sensitivity: str = "free_or_low_cost",
    pref_min: int = 3,
    pref_max: int = 6,
) -> Resident:
    return Resident(
        id=resident_id,
        first_name="Sofia",
        email=f"{resident_id}@example.com",
        preferred_language="English",
        city="Amsterdam",
        neighborhood=None,
        location_radius_km=3,
        social_comfort=social_comfort,
        preferred_group_size_min=pref_min,
        preferred_group_size_max=pref_max,
        cost_sensitivity=cost_sensitivity,
        status="active",
        created_at=_now(),
        updated_at=_now(),
    )


def _pref(value: str, kind: str = "interest", resident_id: str = "resident_test") -> ResidentPreference:
    return ResidentPreference(
        id=f"pref_{kind}_{value}",
        resident_id=resident_id,
        preference_type=kind,  # type: ignore[arg-type]
        value=value,
        created_at=_now(),
    )


def _avail(weekday: str, start: str, end: str, resident_id: str = "resident_test") -> ResidentAvailability:
    return ResidentAvailability(
        id=f"avail_{weekday}_{start}",
        resident_id=resident_id,
        weekday=weekday,  # type: ignore[arg-type]
        start_time_local=start,
        end_time_local=end,
        created_at=_now(),
    )


def _avoid(value: str, resident_id: str = "resident_test") -> ResidentAvoidance:
    return ResidentAvoidance(
        id=f"avoid_{value}",
        resident_id=resident_id,
        value=value,
        created_at=_now(),
    )


def _template(
    *,
    code: str = "photography_walk",
    title: str = "Photography Walk",
    family: str = "walks_outdoor",
    cost: str = "free",
    social_energy: str = "low",
    setting: str = "outdoor",
    intensity: str = "light",
    noise: str = "quiet",
    structure: str = "self_paced",
    risk: str = "low",
    group_min: int = 3,
    group_max: int = 8,
) -> ActivityTemplate:
    return ActivityTemplate(
        id=f"template_{code}",
        code=code,
        title=title,
        description=f"{title} description",
        family=family,
        typical_duration_minutes=90,
        typical_group_size_min=group_min,
        typical_group_size_max=group_max,
        typical_cost_band=cost,  # type: ignore[arg-type]
        social_energy=social_energy,  # type: ignore[arg-type]
        setting=setting,  # type: ignore[arg-type]
        intensity=intensity,  # type: ignore[arg-type]
        noise_level=noise,  # type: ignore[arg-type]
        structure=structure,  # type: ignore[arg-type]
        risk_level=risk,  # type: ignore[arg-type]
        created_at=_now(),
        updated_at=_now(),
    )


class TestVectorizer(unittest.TestCase):
    def test_resident_vector_is_stable_and_non_empty(self) -> None:
        resident = _resident()
        prefs = [
            _pref("photography"),
            _pref("nature"),
            _pref("step_free", kind="accessibility_need"),
        ]
        avails = [_avail("sat", "09:00", "12:00")]
        avoids = [_avoid("loud_music")]

        first = build_resident_vector(resident, prefs, avails, avoids)
        second = build_resident_vector(resident, prefs, avails, avoids)

        self.assertEqual(first.owner_kind, "resident")
        self.assertEqual(first.owner_id, resident.id)
        self.assertGreater(len(first.features), 0)
        self.assertEqual(first.features, second.features)

        self.assertEqual(first.features.get("interest:photography"), 1.0)
        self.assertEqual(first.features.get("interest:nature"), 1.0)
        self.assertEqual(first.features.get("access:step_free"), 1.0)
        self.assertEqual(first.features.get("avoid:loud_music"), AVOIDANCE_WEIGHT)
        self.assertEqual(first.features.get("avail:sat_morning"), 1.0)
        self.assertEqual(first.features.get("social_energy:low"), 1.0)
        self.assertEqual(first.features.get("cost:free"), 1.0)
        self.assertEqual(first.features.get("cost:low"), 1.0)
        for n in (3, 4, 5, 6):
            self.assertEqual(first.features.get(f"group_size:{n}"), 1.0)

    def test_template_vector_is_stable_and_includes_tag_signals(self) -> None:
        template = _template()
        tags = [
            "theme:outdoor",
            "attribute:creative",
            "access:step_free_possible",
            "skill:beginner_friendly",
            "format:meetup",
        ]
        first = build_template_vector(template, tags)
        second = build_template_vector(template, tags)

        self.assertEqual(first.owner_kind, "activity_template")
        self.assertEqual(first.features, second.features)
        self.assertGreater(len(first.features), 0)

        self.assertEqual(first.features.get("family:walks_outdoor"), 1.0)
        self.assertEqual(first.features.get("activity_pref:photography_walk"), 1.0)
        self.assertEqual(first.features.get("theme:outdoor"), 1.0)
        self.assertEqual(first.features.get("interest:outdoor"), 1.0)
        self.assertEqual(first.features.get("attribute:creative"), 1.0)
        self.assertEqual(first.features.get("interest:creative"), 0.7)
        self.assertEqual(first.features.get("access:step_free_possible"), 1.0)
        # title/code token mirror as low-weight interest signals
        self.assertEqual(first.features.get("interest:photography"), 0.6)


class TestCosineSimilarity(unittest.TestCase):
    def test_cosine_is_symmetric_and_bounded(self) -> None:
        a = {"interest:photography": 1.0, "interest:nature": 1.0, "cost:free": 1.0}
        b = {"interest:photography": 0.8, "interest:outdoor": 1.0, "cost:free": 1.0}
        forward = cosine_similarity(a, b)
        backward = cosine_similarity(b, a)
        self.assertAlmostEqual(forward, backward, places=12)
        self.assertGreaterEqual(forward, 0.0)
        self.assertLessEqual(forward, 1.0)

    def test_cosine_identical_vectors_is_one(self) -> None:
        v = {"interest:x": 1.0, "cost:free": 1.0}
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=12)

    def test_cosine_empty_returns_zero(self) -> None:
        self.assertEqual(cosine_similarity({}, {"a": 1.0}), 0.0)
        self.assertEqual(cosine_similarity({"a": 1.0}, {}), 0.0)
        self.assertEqual(cosine_similarity({"a": -1.0}, {"a": 1.0}), 0.0)

    def test_cosine_ignores_negative_components(self) -> None:
        # Negative resident weight (avoidance) does not pull cosine below zero
        a = {"interest:x": 1.0, "avoid:y": -1.5}
        b = {"interest:x": 1.0, "interest:y": 1.0}
        score = cosine_similarity(a, b)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_weighted_total_combines_components(self) -> None:
        breakdown = weighted_total(cosine=0.5, cost_score=1.0, availability_score=1.0)
        # 0.7 * 0.5 + 0.15 * 1.0 + 0.15 * 1.0 = 0.65
        self.assertAlmostEqual(breakdown.total, 0.65, places=6)


class TestHardConstraints(unittest.TestCase):
    def test_avoidance_rejects_matching_template(self) -> None:
        resident = _resident()
        template = _template(code="loud_pub_quiz", title="Loud Pub Quiz", family="pubs_social", noise="loud")
        result = check_template_constraints(
            resident=resident,
            avoidances=[_avoid("pubs_social")],
            template=template,
            template_tags=["theme:nightlife", "attribute:social"],
            accessibility_needs=[],
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(reason.startswith("avoidance:") for reason in result.reasons))

    def test_cost_band_excluded_rejects(self) -> None:
        resident = _resident(cost_sensitivity="free_or_low_cost")
        template = _template(code="spa_workshop", cost="high")
        result = check_template_constraints(
            resident=resident,
            avoidances=[],
            template=template,
            template_tags=[],
            accessibility_needs=[],
        )
        self.assertFalse(result.passed)
        self.assertIn("cost_band_excluded:high", result.reasons)

    def test_group_size_mismatch_rejects(self) -> None:
        resident = _resident(pref_min=3, pref_max=6)
        too_big = _template(code="stadium_event", group_min=20, group_max=40)
        too_small = _template(code="one_on_one_chat", group_min=2, group_max=2)
        self.assertIn(
            "group_size_too_large",
            check_template_constraints(
                resident=resident,
                avoidances=[],
                template=too_big,
                template_tags=[],
                accessibility_needs=[],
            ).reasons,
        )
        self.assertIn(
            "group_size_too_small",
            check_template_constraints(
                resident=resident,
                avoidances=[],
                template=too_small,
                template_tags=[],
                accessibility_needs=[],
            ).reasons,
        )

    def test_low_pressure_resident_rejects_high_energy(self) -> None:
        resident = _resident(social_comfort="small_group_low_pressure")
        template = _template(code="rave_night", social_energy="high", noise="loud")
        result = check_template_constraints(
            resident=resident,
            avoidances=[],
            template=template,
            template_tags=[],
            accessibility_needs=[],
        )
        self.assertIn("social_energy_too_high", result.reasons)

    def test_template_passes_when_compatible(self) -> None:
        resident = _resident()
        template = _template()
        result = check_template_constraints(
            resident=resident,
            avoidances=[],
            template=template,
            template_tags=["theme:outdoor"],
            accessibility_needs=[],
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.reasons, ())


class TestMatchingEngine(unittest.TestCase):
    def _setup_engine(self, conn) -> tuple[MatchingEngine, str]:
        residents = ResidentRepository(conn)
        templates = ActivityTemplateRepository(conn)
        matching = MatchingRepository(conn)
        seed_activity_templates(conn=conn)

        resident = residents.create_resident(
            first_name="Sofia",
            email="sofia.calm@example.com",
            preferred_language="English",
            city="Amsterdam",
            social_comfort="small_group_low_pressure",
            preferred_group_size_min=3,
            preferred_group_size_max=6,
            cost_sensitivity="free_or_low_cost",
        )
        for value in ("photography", "nature", "outdoor"):
            residents.add_preference(
                resident_id=resident.id, preference_type="interest", value=value
            )
        residents.add_preference(
            resident_id=resident.id,
            preference_type="activity",
            value="photography_walk",
        )
        residents.add_availability(
            resident_id=resident.id,
            weekday="sat",
            start_time_local="09:00",
            end_time_local="12:00",
        )
        engine = MatchingEngine(
            residents=residents,
            templates=templates,
            matching=matching,
        )
        return engine, resident.id

    def test_persona_top_candidates_include_photography_walk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine, resident_id = self._setup_engine(conn)
                run_id, top_results = engine.run_matching(
                    resident_id=resident_id, top_n=3
                )

                self.assertNotEqual(run_id, "")
                self.assertGreaterEqual(len(top_results), 1)
                top_codes = [r.template.code for r in top_results]
                self.assertIn(
                    "photography_walk",
                    top_codes,
                    f"photography_walk should appear in top 3, got {top_codes}",
                )
                top = top_results[0]
                self.assertTrue(top.constraint.passed)
                self.assertGreater(top.breakdown.total, 0.0)
                self.assertLessEqual(top.breakdown.total, 1.0)
                self.assertGreater(top.breakdown.cosine, 0.0)

    def test_run_persists_all_artifact_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine, resident_id = self._setup_engine(conn)
                run_id, top_results = engine.run_matching(
                    resident_id=resident_id, top_n=5
                )
                self.assertNotEqual(run_id, "")
                self.assertGreaterEqual(len(top_results), 1)

                runs_count = conn.execute(
                    "SELECT COUNT(*) FROM matching_runs WHERE id = ?", (run_id,)
                ).fetchone()[0]
                self.assertEqual(runs_count, 1)

                candidates_count = conn.execute(
                    "SELECT COUNT(*) FROM match_candidates WHERE matching_run_id = ?",
                    (run_id,),
                ).fetchone()[0]
                self.assertGreater(candidates_count, 0)

                feature_scores_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM match_feature_scores fs
                    JOIN match_candidates c ON c.id = fs.match_candidate_id
                    WHERE c.matching_run_id = ?
                    """,
                    (run_id,),
                ).fetchone()[0]
                self.assertGreater(feature_scores_count, 0)

                explanations_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM match_explanations e
                    JOIN match_candidates c ON c.id = e.match_candidate_id
                    WHERE c.matching_run_id = ?
                    """,
                    (run_id,),
                ).fetchone()[0]
                self.assertEqual(explanations_count, candidates_count)

                similarity_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM resident_activity_similarity
                    WHERE resident_id = ? AND model_version = ?
                    """,
                    (resident_id, DEFAULT_MODEL_VERSION),
                ).fetchone()[0]
                self.assertGreater(similarity_count, 0)

                resident_weights = conn.execute(
                    """
                    SELECT COUNT(*) FROM resident_feature_weights
                    WHERE resident_id = ? AND model_version = ?
                    """,
                    (resident_id, DEFAULT_MODEL_VERSION),
                ).fetchone()[0]
                self.assertGreater(resident_weights, 0)

                activity_weights = conn.execute(
                    """
                    SELECT COUNT(*) FROM activity_feature_weights
                    WHERE model_version = ?
                    """,
                    (DEFAULT_MODEL_VERSION,),
                ).fetchone()[0]
                self.assertGreater(activity_weights, 0)

                top_payload = conn.execute(
                    """
                    SELECT e.explanation_json
                    FROM match_explanations e
                    JOIN match_candidates c ON c.id = e.match_candidate_id
                    WHERE c.matching_run_id = ? AND c.rank_position = 1
                    """,
                    (run_id,),
                ).fetchone()[0]
                payload = json.loads(top_payload)
                self.assertEqual(payload["model_version"], DEFAULT_MODEL_VERSION)
                self.assertIn("score_breakdown", payload)
                self.assertIn("top_features", payload)
                self.assertTrue(payload["constraints"]["passed"])

    def test_two_runs_produce_same_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine, resident_id = self._setup_engine(conn)
                _, first = engine.run_matching(resident_id=resident_id, top_n=10)
                _, second = engine.run_matching(resident_id=resident_id, top_n=10)

                first_codes = [r.template.code for r in first]
                second_codes = [r.template.code for r in second]
                self.assertEqual(first_codes, second_codes)
                for r1, r2 in zip(first, second):
                    self.assertAlmostEqual(r1.breakdown.total, r2.breakdown.total, places=12)
                    self.assertAlmostEqual(r1.breakdown.cosine, r2.breakdown.cosine, places=12)

    def test_run_emits_info_logs_at_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine, resident_id = self._setup_engine(conn)
                with self.assertLogs("app.matching.engine", level="INFO") as captured:
                    engine.run_matching(resident_id=resident_id, top_n=3)
                logs = "\n".join(captured.output)
                self.assertIn("matching.run start", logs)
                self.assertIn("matching.run top", logs)
                self.assertIn("matching.run end", logs)

    def test_vectorizer_emits_debug_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                engine, resident_id = self._setup_engine(conn)
                with self.assertLogs("app.matching.vectorizer", level="DEBUG") as captured:
                    engine.run_matching(resident_id=resident_id, top_n=1)
                logs = "\n".join(captured.output)
                self.assertIn("vectorizer.resident", logs)
                self.assertIn("vectorizer.template", logs)

    def test_engine_skips_avoidance_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                residents = ResidentRepository(conn)
                templates_repo = ActivityTemplateRepository(conn)
                matching = MatchingRepository(conn)
                seed_activity_templates(conn=conn)

                resident = residents.create_resident(
                    first_name="Luca",
                    email="luca@example.com",
                    preferred_language="English",
                    city="Amsterdam",
                    social_comfort="small_group_low_pressure",
                    preferred_group_size_min=3,
                    preferred_group_size_max=6,
                    cost_sensitivity="free_or_low_cost",
                )
                residents.add_avoidance(resident_id=resident.id, value="pubs_social")

                engine = MatchingEngine(
                    residents=residents,
                    templates=templates_repo,
                    matching=matching,
                )
                run_id, top_results = engine.run_matching(
                    resident_id=resident.id, top_n=20
                )

                self.assertNotEqual(run_id, "")
                top_families = {
                    templates_repo.get_template_by_code(r.template.code).family  # type: ignore[union-attr]
                    for r in top_results
                }
                self.assertNotIn("pubs_social", top_families)

                rejected_rows = conn.execute(
                    """
                    SELECT activity_id FROM match_candidates
                    WHERE matching_run_id = ? AND hard_constraints_passed = 0
                    """,
                    (run_id,),
                ).fetchall()
                self.assertGreater(len(rejected_rows), 0)


if __name__ == "__main__":
    unittest.main()
