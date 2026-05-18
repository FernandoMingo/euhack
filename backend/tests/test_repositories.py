from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    ActivityRepository,
    MatchingRepository,
    RatingRepository,
    ResidentRepository,
    connect,
    init_db,
)


class TestRepositories(unittest.TestCase):
    def test_resident_activity_matching_rating_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(db_path=db_path)

            with connect(db_path=db_path) as conn:
                residents = ResidentRepository(conn)
                activities = ActivityRepository(conn)
                matching = MatchingRepository(conn)
                ratings = RatingRepository(conn)

                resident = residents.create_resident(
                    first_name="Sofia",
                    email="sofia@example.com",
                    preferred_language="English",
                    city="Amsterdam",
                    social_comfort="small_group_low_pressure",
                    preferred_group_size_min=3,
                    preferred_group_size_max=6,
                    cost_sensitivity="free_or_low_cost",
                )
                other_resident = residents.create_resident(
                    first_name="Luca",
                    email="luca@example.com",
                    preferred_language="English",
                    city="Amsterdam",
                    social_comfort="small_group_low_pressure",
                    preferred_group_size_min=3,
                    preferred_group_size_max=6,
                    cost_sensitivity="free_or_low_cost",
                )
                residents.add_preference(
                    resident_id=resident.id,
                    preference_type="interest",
                    value="photography",
                )

                venue = activities.create_venue(
                    name="Vondelpark Entrance",
                    address="Vondelpark, Amsterdam",
                    city="Amsterdam",
                    lat=52.3579,
                    lng=4.8686,
                )
                host = activities.create_host(
                    full_name="Nora",
                    host_type="volunteer",
                )
                activity = activities.create_activity(
                    title="Calm Photography Walk",
                    activity_type="photography_walk",
                    venue_id=venue.id,
                    host_id=host.id,
                    start_at="2026-05-23T10:30:00+00:00",
                    end_at="2026-05-23T12:00:00+00:00",
                    capacity=6,
                    risk_level="low",
                    approval_status="approved",
                )
                circle = activities.create_circle(
                    activity_id=activity.id,
                    status="invitations_sent",
                    fit_score=0.91,
                    shared_signals_json='["photography","parks"]',
                )
                activities.add_circle_member(circle_id=circle.id, resident_id=resident.id)
                invitation = activities.create_invitation(
                    circle_id=circle.id,
                    activity_id=activity.id,
                    resident_id=resident.id,
                )
                activities.update_invitation_status(
                    invitation_id=invitation.id, status="accepted"
                )
                activities.record_attendance(
                    activity_id=activity.id,
                    resident_id=resident.id,
                    attendance_status="attended",
                    check_in_at="2026-05-23T10:28:00+00:00",
                )
                activities.add_feedback(
                    activity_id=activity.id,
                    resident_id=resident.id,
                    felt_after="better",
                    activity_fit=True,
                    group_comfort=True,
                    would_repeat=True,
                )

                run = matching.create_matching_run(
                    run_type="activity_ranking",
                    model_version="v1",
                    score_algorithm="weighted_sum",
                )
                candidate = matching.add_match_candidate(
                    matching_run_id=run.id,
                    resident_id=resident.id,
                    circle_id=circle.id,
                    activity_id=activity.id,
                    total_score=0.91,
                    rank_position=1,
                    hard_constraints_passed=True,
                )
                matching.add_feature_score(
                    match_candidate_id=candidate.id,
                    feature_key="interest_overlap",
                    feature_weight=0.25,
                    feature_score=0.95,
                    contribution=0.2375,
                )
                matching.upsert_resident_feature_weight(
                    resident_id=resident.id,
                    feature_key="interest_photography",
                    feature_weight=1.0,
                    model_version="v1",
                )
                matching.upsert_activity_feature_weight(
                    activity_id=activity.id,
                    feature_key="interest_photography",
                    feature_weight=0.9,
                    model_version="v1",
                )
                similarity = matching.upsert_similarity(
                    resident_id=resident.id,
                    activity_id=activity.id,
                    algorithm="cosine",
                    model_version="v1",
                    similarity_score=0.97,
                )
                self.assertGreater(similarity.similarity_score, 0.9)

                peer_rating = ratings.create_peer_rating(
                    activity_id=activity.id,
                    rater_resident_id=resident.id,
                    ratee_resident_id=other_resident.id,
                    comfort_to_be_with=4,
                    respectful_behavior=5,
                    reliability_showed_up=5,
                    group_contribution=4,
                )
                rollup = ratings.upsert_peer_rollup(
                    resident_id=other_resident.id,
                    model_version="v1",
                    comfort_to_be_with_score=4.0,
                    respectful_behavior_score=5.0,
                    reliability_showed_up_score=5.0,
                    group_contribution_score=4.0,
                    rating_count=1,
                    confidence=0.8,
                    recentness_weighted_score=4.5,
                )
                ratings.flag_peer_rating(
                    peer_rating_id=peer_rating.id,
                    flag_type="outlier",
                    severity="low",
                    details="single unusual variance",
                )
                listed = ratings.list_ratings_for_resident(resident_id=other_resident.id)

                self.assertEqual(rollup.rating_count, 1)
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0].id, peer_rating.id)


if __name__ == "__main__":
    unittest.main()

