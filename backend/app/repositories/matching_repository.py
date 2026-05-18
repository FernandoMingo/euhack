from __future__ import annotations

from app.dataclasses import (
    FeatureWeight,
    GraphEdge,
    GraphScore,
    MatchCandidate,
    MatchExplanation,
    MatchFeatureScore,
    MatchingRun,
    ResidentActivitySimilarity,
)
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


class MatchingRepository(RepositoryBase):
    def create_matching_run(
        self,
        *,
        run_type: str,
        model_version: str,
        score_algorithm: str,
        source_window_start: str | None = None,
        source_window_end: str | None = None,
    ) -> MatchingRun:
        run_id = new_id("match_run")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO matching_runs (
                id, run_type, model_version, score_algorithm, source_window_start, source_window_end, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, run_type, model_version, score_algorithm, source_window_start, source_window_end, now),
        )
        return MatchingRun(
            id=run_id,
            run_type=run_type,  # type: ignore[arg-type]
            model_version=model_version,
            score_algorithm=score_algorithm,
            source_window_start=parse_dt(source_window_start),
            source_window_end=parse_dt(source_window_end),
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def add_match_candidate(
        self,
        *,
        matching_run_id: str,
        total_score: float,
        rank_position: int,
        hard_constraints_passed: bool,
        resident_id: str | None = None,
        circle_id: str | None = None,
        activity_id: str | None = None,
    ) -> MatchCandidate:
        candidate_id = new_id("candidate")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO match_candidates (
                id, matching_run_id, resident_id, circle_id, activity_id,
                total_score, rank_position, hard_constraints_passed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                matching_run_id,
                resident_id,
                circle_id,
                activity_id,
                total_score,
                rank_position,
                int(hard_constraints_passed),
                now,
            ),
        )
        return MatchCandidate(
            id=candidate_id,
            matching_run_id=matching_run_id,
            resident_id=resident_id,
            circle_id=circle_id,
            activity_id=activity_id,
            total_score=total_score,
            rank_position=rank_position,
            hard_constraints_passed=hard_constraints_passed,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def add_feature_score(
        self,
        *,
        match_candidate_id: str,
        feature_key: str,
        feature_weight: float,
        feature_score: float,
        contribution: float,
    ) -> MatchFeatureScore:
        feature_score_id = new_id("feature_score")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO match_feature_scores (
                id, match_candidate_id, feature_key, feature_weight, feature_score, contribution, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (feature_score_id, match_candidate_id, feature_key, feature_weight, feature_score, contribution, now),
        )
        return MatchFeatureScore(
            id=feature_score_id,
            match_candidate_id=match_candidate_id,
            feature_key=feature_key,
            feature_weight=feature_weight,
            feature_score=feature_score,
            contribution=contribution,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def add_explanation(self, *, match_candidate_id: str, summary_text: str, explanation_json: str) -> MatchExplanation:
        explanation_id = new_id("explain")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO match_explanations (id, match_candidate_id, summary_text, explanation_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (explanation_id, match_candidate_id, summary_text, explanation_json, now),
        )
        return MatchExplanation(
            id=explanation_id,
            match_candidate_id=match_candidate_id,
            summary_text=summary_text,
            explanation_json=explanation_json,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def upsert_resident_feature_weight(
        self, *, resident_id: str, feature_key: str, feature_weight: float, model_version: str
    ) -> FeatureWeight:
        feature_weight_id = new_id("rfeat")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_feature_weights (
                id, resident_id, feature_key, feature_weight, model_version, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(resident_id, feature_key, model_version) DO UPDATE SET
                feature_weight = excluded.feature_weight,
                computed_at = excluded.computed_at
            """,
            (feature_weight_id, resident_id, feature_key, feature_weight, model_version, now),
        )
        row = self.fetchone(
            """
            SELECT id, resident_id, feature_key, feature_weight, model_version, computed_at
            FROM resident_feature_weights
            WHERE resident_id = ? AND feature_key = ? AND model_version = ?
            """,
            (resident_id, feature_key, model_version),
        )
        return FeatureWeight(
            id=row["id"],  # type: ignore[index]
            resident_id=row["resident_id"],  # type: ignore[index]
            activity_id=None,
            feature_key=row["feature_key"],  # type: ignore[index]
            feature_weight=row["feature_weight"],  # type: ignore[index]
            model_version=row["model_version"],  # type: ignore[index]
            computed_at=parse_dt(row["computed_at"]),  # type: ignore[index,arg-type]
        )

    def upsert_activity_feature_weight(
        self, *, activity_id: str, feature_key: str, feature_weight: float, model_version: str
    ) -> FeatureWeight:
        feature_weight_id = new_id("afeat")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO activity_feature_weights (
                id, activity_id, feature_key, feature_weight, model_version, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, feature_key, model_version) DO UPDATE SET
                feature_weight = excluded.feature_weight,
                computed_at = excluded.computed_at
            """,
            (feature_weight_id, activity_id, feature_key, feature_weight, model_version, now),
        )
        row = self.fetchone(
            """
            SELECT id, activity_id, feature_key, feature_weight, model_version, computed_at
            FROM activity_feature_weights
            WHERE activity_id = ? AND feature_key = ? AND model_version = ?
            """,
            (activity_id, feature_key, model_version),
        )
        return FeatureWeight(
            id=row["id"],  # type: ignore[index]
            resident_id=None,
            activity_id=row["activity_id"],  # type: ignore[index]
            feature_key=row["feature_key"],  # type: ignore[index]
            feature_weight=row["feature_weight"],  # type: ignore[index]
            model_version=row["model_version"],  # type: ignore[index]
            computed_at=parse_dt(row["computed_at"]),  # type: ignore[index,arg-type]
        )

    def upsert_similarity(
        self,
        *,
        resident_id: str,
        activity_id: str,
        algorithm: str,
        model_version: str,
        similarity_score: float,
    ) -> ResidentActivitySimilarity:
        similarity_id = new_id("similarity")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_activity_similarity (
                id, resident_id, activity_id, algorithm, model_version, similarity_score, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(resident_id, activity_id, algorithm, model_version) DO UPDATE SET
                similarity_score = excluded.similarity_score,
                computed_at = excluded.computed_at
            """,
            (similarity_id, resident_id, activity_id, algorithm, model_version, similarity_score, now),
        )
        row = self.fetchone(
            """
            SELECT id, resident_id, activity_id, algorithm, model_version, similarity_score, computed_at
            FROM resident_activity_similarity
            WHERE resident_id = ? AND activity_id = ? AND algorithm = ? AND model_version = ?
            """,
            (resident_id, activity_id, algorithm, model_version),
        )
        return ResidentActivitySimilarity(
            id=row["id"],  # type: ignore[index]
            resident_id=row["resident_id"],  # type: ignore[index]
            activity_id=row["activity_id"],  # type: ignore[index]
            algorithm=row["algorithm"],  # type: ignore[index]
            model_version=row["model_version"],  # type: ignore[index]
            similarity_score=row["similarity_score"],  # type: ignore[index]
            computed_at=parse_dt(row["computed_at"]),  # type: ignore[index,arg-type]
        )

    def add_graph_edge(
        self,
        *,
        src_type: str,
        src_id: str,
        dst_type: str,
        dst_id: str,
        edge_type: str,
        edge_weight: float,
    ) -> GraphEdge:
        edge_id = new_id("edge")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO graph_edges (id, src_type, src_id, dst_type, dst_id, edge_type, edge_weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (edge_id, src_type, src_id, dst_type, dst_id, edge_type, edge_weight, now),
        )
        return GraphEdge(
            id=edge_id,
            src_type=src_type,  # type: ignore[arg-type]
            src_id=src_id,
            dst_type=dst_type,  # type: ignore[arg-type]
            dst_id=dst_id,
            edge_type=edge_type,
            edge_weight=edge_weight,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def upsert_graph_score(
        self,
        *,
        entity_type: str,
        entity_id: str,
        algorithm: str,
        model_version: str,
        score: float,
        sample_size: int | None = None,
    ) -> GraphScore:
        graph_score_id = new_id("gscore")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO graph_scores (
                id, entity_type, entity_id, algorithm, model_version, score, sample_size, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id, algorithm, model_version) DO UPDATE SET
                score = excluded.score,
                sample_size = excluded.sample_size,
                computed_at = excluded.computed_at
            """,
            (graph_score_id, entity_type, entity_id, algorithm, model_version, score, sample_size, now),
        )
        row = self.fetchone(
            """
            SELECT id, entity_type, entity_id, algorithm, model_version, score, sample_size, computed_at
            FROM graph_scores
            WHERE entity_type = ? AND entity_id = ? AND algorithm = ? AND model_version = ?
            """,
            (entity_type, entity_id, algorithm, model_version),
        )
        return GraphScore(
            id=row["id"],  # type: ignore[index]
            entity_type=row["entity_type"],  # type: ignore[index,arg-type]
            entity_id=row["entity_id"],  # type: ignore[index]
            algorithm=row["algorithm"],  # type: ignore[index]
            model_version=row["model_version"],  # type: ignore[index]
            score=row["score"],  # type: ignore[index]
            sample_size=row["sample_size"],  # type: ignore[index]
            computed_at=parse_dt(row["computed_at"]),  # type: ignore[index,arg-type]
        )

    def get_top_candidates(self, *, matching_run_id: str, limit: int = 5) -> list[MatchCandidate]:
        rows = self.fetchall(
            """
            SELECT * FROM match_candidates
            WHERE matching_run_id = ?
            ORDER BY rank_position ASC
            LIMIT ?
            """,
            (matching_run_id, limit),
        )
        return [
            MatchCandidate(
                id=row["id"],
                matching_run_id=row["matching_run_id"],
                resident_id=row["resident_id"],
                circle_id=row["circle_id"],
                activity_id=row["activity_id"],
                total_score=row["total_score"],
                rank_position=row["rank_position"],
                hard_constraints_passed=bool(row["hard_constraints_passed"]),
                created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            )
            for row in rows
        ]

    def list_candidate_review_rows(
        self,
        *,
        matching_run_id: str,
        limit: int = 100,
    ):
        """Return candidates joined with explanations for operator review."""
        return self.fetchall(
            """
            SELECT
                c.id AS candidate_id,
                c.matching_run_id,
                c.resident_id,
                c.circle_id,
                c.activity_id,
                c.total_score,
                c.rank_position,
                c.hard_constraints_passed,
                c.created_at AS candidate_created_at,
                e.id AS explanation_id,
                e.summary_text,
                e.explanation_json,
                e.created_at AS explanation_created_at
            FROM match_candidates c
            LEFT JOIN match_explanations e ON e.match_candidate_id = c.id
            WHERE c.matching_run_id = ?
            ORDER BY c.rank_position ASC, c.id
            LIMIT ?
            """,
            (matching_run_id, limit),
        )

