from __future__ import annotations

from app.dataclasses import PeerRating, PeerRatingFlag, PeerRatingRollup
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


class RatingRepository(RepositoryBase):
    def create_peer_rating(
        self,
        *,
        activity_id: str,
        rater_resident_id: str,
        ratee_resident_id: str,
        comfort_to_be_with: int | None = None,
        respectful_behavior: int | None = None,
        reliability_showed_up: int | None = None,
        group_contribution: int | None = None,
        note_text: str | None = None,
    ) -> PeerRating:
        rating_id = new_id("peer_rating")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO peer_ratings (
                id, activity_id, rater_resident_id, ratee_resident_id,
                comfort_to_be_with, respectful_behavior, reliability_showed_up,
                group_contribution, note_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, rater_resident_id, ratee_resident_id) DO UPDATE SET
                comfort_to_be_with = excluded.comfort_to_be_with,
                respectful_behavior = excluded.respectful_behavior,
                reliability_showed_up = excluded.reliability_showed_up,
                group_contribution = excluded.group_contribution,
                note_text = excluded.note_text,
                updated_at = excluded.updated_at
            """,
            (
                rating_id,
                activity_id,
                rater_resident_id,
                ratee_resident_id,
                comfort_to_be_with,
                respectful_behavior,
                reliability_showed_up,
                group_contribution,
                note_text,
                now,
                now,
            ),
        )
        row = self.fetchone(
            """
            SELECT * FROM peer_ratings
            WHERE activity_id = ? AND rater_resident_id = ? AND ratee_resident_id = ?
            """,
            (activity_id, rater_resident_id, ratee_resident_id),
        )
        return PeerRating(
            id=row["id"],  # type: ignore[index]
            activity_id=row["activity_id"],  # type: ignore[index]
            rater_resident_id=row["rater_resident_id"],  # type: ignore[index]
            ratee_resident_id=row["ratee_resident_id"],  # type: ignore[index]
            comfort_to_be_with=row["comfort_to_be_with"],  # type: ignore[index]
            respectful_behavior=row["respectful_behavior"],  # type: ignore[index]
            reliability_showed_up=row["reliability_showed_up"],  # type: ignore[index]
            group_contribution=row["group_contribution"],  # type: ignore[index]
            note_text=row["note_text"],  # type: ignore[index]
            created_at=parse_dt(row["created_at"]),  # type: ignore[index,arg-type]
            updated_at=parse_dt(row["updated_at"]),  # type: ignore[index,arg-type]
        )

    def upsert_peer_rollup(
        self,
        *,
        resident_id: str,
        model_version: str,
        comfort_to_be_with_score: float | None = None,
        respectful_behavior_score: float | None = None,
        reliability_showed_up_score: float | None = None,
        group_contribution_score: float | None = None,
        rating_count: int = 0,
        confidence: float | None = None,
        recentness_weighted_score: float | None = None,
    ) -> PeerRatingRollup:
        rollup_id = new_id("peer_rollup")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO peer_rating_rollups (
                id, resident_id, model_version, comfort_to_be_with_score, respectful_behavior_score,
                reliability_showed_up_score, group_contribution_score, rating_count, confidence,
                recentness_weighted_score, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(resident_id, model_version) DO UPDATE SET
                comfort_to_be_with_score = excluded.comfort_to_be_with_score,
                respectful_behavior_score = excluded.respectful_behavior_score,
                reliability_showed_up_score = excluded.reliability_showed_up_score,
                group_contribution_score = excluded.group_contribution_score,
                rating_count = excluded.rating_count,
                confidence = excluded.confidence,
                recentness_weighted_score = excluded.recentness_weighted_score,
                computed_at = excluded.computed_at
            """,
            (
                rollup_id,
                resident_id,
                model_version,
                comfort_to_be_with_score,
                respectful_behavior_score,
                reliability_showed_up_score,
                group_contribution_score,
                rating_count,
                confidence,
                recentness_weighted_score,
                now,
            ),
        )
        row = self.fetchone(
            "SELECT * FROM peer_rating_rollups WHERE resident_id = ? AND model_version = ?",
            (resident_id, model_version),
        )
        return PeerRatingRollup(
            id=row["id"],  # type: ignore[index]
            resident_id=row["resident_id"],  # type: ignore[index]
            model_version=row["model_version"],  # type: ignore[index]
            comfort_to_be_with_score=row["comfort_to_be_with_score"],  # type: ignore[index]
            respectful_behavior_score=row["respectful_behavior_score"],  # type: ignore[index]
            reliability_showed_up_score=row["reliability_showed_up_score"],  # type: ignore[index]
            group_contribution_score=row["group_contribution_score"],  # type: ignore[index]
            rating_count=row["rating_count"],  # type: ignore[index]
            confidence=row["confidence"],  # type: ignore[index]
            recentness_weighted_score=row["recentness_weighted_score"],  # type: ignore[index]
            computed_at=parse_dt(row["computed_at"]),  # type: ignore[index,arg-type]
        )

    def flag_peer_rating(
        self,
        *,
        peer_rating_id: str,
        flag_type: str,
        severity: str,
        details: str | None = None,
    ) -> PeerRatingFlag:
        flag_id = new_id("peer_flag")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO peer_rating_flags (id, peer_rating_id, flag_type, severity, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (flag_id, peer_rating_id, flag_type, severity, details, now),
        )
        return PeerRatingFlag(
            id=flag_id,
            peer_rating_id=peer_rating_id,
            flag_type=flag_type,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            details=details,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def list_ratings_for_resident(self, *, resident_id: str, limit: int = 100) -> list[PeerRating]:
        rows = self.fetchall(
            """
            SELECT * FROM peer_ratings
            WHERE ratee_resident_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (resident_id, limit),
        )
        return [
            PeerRating(
                id=row["id"],
                activity_id=row["activity_id"],
                rater_resident_id=row["rater_resident_id"],
                ratee_resident_id=row["ratee_resident_id"],
                comfort_to_be_with=row["comfort_to_be_with"],
                respectful_behavior=row["respectful_behavior"],
                reliability_showed_up=row["reliability_showed_up"],
                group_contribution=row["group_contribution"],
                note_text=row["note_text"],
                created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
                updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
            )
            for row in rows
        ]

