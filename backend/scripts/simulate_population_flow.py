from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import DB_PATH, engine
from app.main import app
from app.models import Activity

OPERATOR_HEADERS = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
PROFESSIONAL_HEADERS = {"x-actor-role": "professional", "x-actor-id": "professional_456"}


INTEREST_POOL = [
    "photography",
    "parks",
    "coffee",
    "museums",
    "gardening",
    "board games",
    "walking",
    "community",
    "art",
    "volunteering",
]

ACTIVITY_BLUEPRINTS = [
    {"id": "activity_sim_001", "title": "Sunrise Park Walk", "type": "park_walk", "cost": 0, "risk_level": "low"},
    {"id": "activity_sim_002", "title": "Museum Discovery", "type": "museum_visit", "cost": 8, "risk_level": "low"},
    {"id": "activity_sim_003", "title": "Community Garden Hour", "type": "community_gardening", "cost": 0, "risk_level": "low"},
    {"id": "activity_sim_004", "title": "Coffee and Board Games", "type": "board_games", "cost": 5, "risk_level": "low"},
    {"id": "activity_sim_005", "title": "Neighborhood Photo Route", "type": "photography_walk", "cost": 0, "risk_level": "low"},
]


@dataclass
class SimResident:
    resident_id: str
    first_name: str
    email: str
    neighborhood: str
    language: str
    interests: list[str]
    avoid: list[str]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate fake users and run full matching flow.")
    parser.add_argument("--users", type=int, default=30, help="Number of fake residents to generate")
    parser.add_argument("--group-size", type=int, default=5, help="Residents per matching cohort")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Directory (relative to backend/) to write simulation outputs",
    )
    return parser.parse_args()


def _reset_database() -> None:
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()


def _create_extra_activities() -> None:
    with Session(engine) as session:
        for index, blueprint in enumerate(ACTIVITY_BLUEPRINTS, start=1):
            start = datetime.fromisoformat(f"2026-05-{20 + index:02d}T10:30:00+02:00")
            end = datetime.fromisoformat(f"2026-05-{20 + index:02d}T12:00:00+02:00")
            session.merge(
                Activity(
                    id=blueprint["id"],
                    title=blueprint["title"],
                    type=blueprint["type"],
                    location={
                        "name": f"Amsterdam Spot {index}",
                        "address": f"Area {index}, Amsterdam",
                        "lat": 52.35 + (index * 0.005),
                        "lng": 4.86 + (index * 0.005),
                    },
                    start_time=start,
                    end_time=end,
                    capacity=8,
                    host_id=f"host_sim_{index:03d}",
                    cost=blueprint["cost"],
                    accessibility=["step_free_route"],
                    risk_level=blueprint["risk_level"],
                    approval_status="generated",
                    lifecycle_status="generated",
                )
            )
        session.commit()


def _fake_residents(count: int, seed: int) -> list[SimResident]:
    rng = random.Random(seed)
    neighborhoods = ["Oud-West", "De Pijp", "Centrum", "Noord", "Oost", "West"]
    languages = ["English", "Dutch", "English", "English", "Dutch"]
    residents: list[SimResident] = []
    for i in range(1, count + 1):
        resident_id = f"resident_sim_{i:03d}"
        residents.append(
            SimResident(
                resident_id=resident_id,
                first_name=f"User{i}",
                email=f"user{i}@example.com",
                neighborhood=rng.choice(neighborhoods),
                language=rng.choice(languages),
                interests=sorted(rng.sample(INTEREST_POOL, 3)),
                avoid=rng.sample(["alcohol", "loud venues", "late night"], k=1),
            )
        )
    return residents


def _create_resident_via_api(client: TestClient, resident: SimResident) -> None:
    referral_payload = {
        "resident_id": resident.resident_id,
        "first_name": resident.first_name,
        "email": resident.email,
        "preferred_language": resident.language,
        "consent_given": True,
        "consent_scope": [
            "create_social_profile",
            "use_profile_for_activity_matching",
            "send_activity_invitations",
            "share_limited_status_with_professional",
        ],
    }
    profile_payload = {
        "approx_location": {
            "city": "Amsterdam",
            "neighborhood": resident.neighborhood,
            "lat": 52.35 + ((hash(resident.resident_id) % 100) / 1000.0),
            "lng": 4.85 + ((hash(resident.first_name) % 100) / 1000.0),
        },
        "location_radius_km": 4,
        "interests": resident.interests,
        "activity_preferences": resident.interests,
        "availability": ["Saturday morning", "Sunday afternoon"],
        "social_comfort": "small_group_low_pressure",
        "preferred_group_size": {"min": 3, "max": 6},
        "accessibility_needs": ["step_free_route"],
        "cost_sensitivity": "free_or_low_cost",
        "avoid": resident.avoid,
        "profile_visibility": {"first_name": True, "conversation_starter": True},
    }

    referral = client.post("/api/residents/referral", json=referral_payload, headers=PROFESSIONAL_HEADERS)
    if referral.status_code not in {200, 201}:
        raise RuntimeError(f"Referral failed for {resident.resident_id}: {referral.status_code} {referral.json()}")
    profile = client.post(
        f"/api/residents/{resident.resident_id}/profile",
        json=profile_payload,
        headers=PROFESSIONAL_HEADERS,
    )
    if profile.status_code != 200:
        raise RuntimeError(f"Profile failed for {resident.resident_id}: {profile.status_code} {profile.json()}")


def _cohorts(resident_ids: list[str], group_size: int) -> list[list[str]]:
    return [resident_ids[i : i + group_size] for i in range(0, len(resident_ids), group_size) if len(resident_ids[i : i + group_size]) >= 3]


def _run_cohort_flow(client: TestClient, cohort_ids: list[str], cohort_index: int) -> dict:
    circle_resp = client.post(
        "/api/ai/generate-circles",
        json={"resident_ids": cohort_ids},
        headers=OPERATOR_HEADERS,
    )
    circle_resp.raise_for_status()
    generated_circle = circle_resp.json()["data"]
    generated_activity_id = generated_circle["activity_id"]

    ranking_resp = client.post(
        "/api/ai/rank-activities",
        json={"resident_ids": cohort_ids},
        headers=OPERATOR_HEADERS,
    )
    ranking_resp.raise_for_status()
    ranked = ranking_resp.json()["data"]["ranked_activities"]
    top_activity_id = ranked[0]["activity_id"]

    explain_resp = client.post(
        "/api/ai/explain-match",
        json={"resident_ids": cohort_ids, "activity_id": top_activity_id},
        headers=OPERATOR_HEADERS,
    )
    explain_resp.raise_for_status()
    explanation = explain_resp.json()["data"]

    proposal_resp = client.post(
        "/api/ai/generate-activity-proposal",
        json={"resident_ids": cohort_ids, "activity_ids": [generated_activity_id]},
        headers=OPERATOR_HEADERS,
    )
    proposal_resp.raise_for_status()
    proposal = proposal_resp.json()["data"]
    proposal_id = proposal["proposal_id"]

    approve_resp = client.post(
        f"/api/operator/proposals/{proposal_id}/approve",
        json={"reason_code": f"SIM_COHORT_{cohort_index:02d}_APPROVED"},
        headers=OPERATOR_HEADERS,
    )
    approve_resp.raise_for_status()

    resident_invites: list[dict] = []
    for resident_id in cohort_ids:
        resident_headers = {"x-actor-role": "resident", "x-actor-id": resident_id}
        invites_resp = client.get("/api/resident/invitations", headers=resident_headers)
        invites_resp.raise_for_status()
        invites = invites_resp.json()["data"]
        accepted = 0
        for invite in invites:
            if invite["activity_id"] == proposal_id and invite["status"] == "sent":
                accept_resp = client.post(f"/api/invitations/{invite['id']}/accept", headers=resident_headers)
                if accept_resp.status_code == 200:
                    accepted += 1
        resident_invites.append({"resident_id": resident_id, "invite_count": len(invites), "accepted_for_top_activity": accepted})

    return {
        "cohort_index": cohort_index,
        "resident_ids": cohort_ids,
        "top_activity_id": top_activity_id,
        "generated_circle_activity_id": generated_activity_id,
        "top_fit_score": ranked[0]["fit_score"],
        "ranked_activities": ranked[:3],
        "top_positive_signals": explanation["top_positive_signals"],
        "hard_constraints_passed": explanation["hard_constraints_passed"],
        "approval_status": "approved",
        "resident_invitation_stats": resident_invites,
    }


def _build_markdown_report(run_result: dict) -> str:
    lines: list[str] = []
    lines.append("# CivicCircles Simulation Report")
    lines.append("")
    lines.append(f"- Generated residents: **{run_result['generated_residents']}**")
    lines.append(f"- Cohorts processed: **{len(run_result['cohorts'])}**")
    lines.append(f"- Group size: **{run_result['group_size']}**")
    lines.append("")
    lines.append("## Cohort Results")
    lines.append("")
    for cohort in run_result["cohorts"]:
        lines.append(f"### Cohort {cohort['cohort_index']:02d}")
        lines.append(f"- Residents: `{', '.join(cohort['resident_ids'])}`")
        lines.append(f"- Suggested top activity: `{cohort['top_activity_id']}` (fit `{cohort['top_fit_score']}`)")
        lines.append(f"- Activity used for approved circle: `{cohort['generated_circle_activity_id']}`")
        lines.append(f"- Top signals: `{', '.join(cohort['top_positive_signals'])}`")
        lines.append(f"- Constraints passed: `{', '.join(cohort['hard_constraints_passed'])}`")
        lines.append("- Top 3 ranked activities:")
        for item in cohort["ranked_activities"]:
            lines.append(f"  - `{item['activity_id']}` score `{item['fit_score']}`")
        total_accepts = sum(row["accepted_for_top_activity"] for row in cohort["resident_invitation_stats"])
        lines.append(f"- Invitations accepted for top activity: **{total_accepts}/{len(cohort['resident_ids'])}**")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    _reset_database()
    output_dir = (Path(__file__).resolve().parents[1] / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    fake_residents = _fake_residents(args.users, args.seed)
    run_result: dict = {
        "generated_residents": args.users,
        "group_size": args.group_size,
        "seed": args.seed,
        "cohorts": [],
    }

    with TestClient(app) as client:
        _create_extra_activities()
        for resident in fake_residents:
            _create_resident_via_api(client, resident)

        cohorts = _cohorts([user.resident_id for user in fake_residents], args.group_size)
        for index, cohort_ids in enumerate(cohorts, start=1):
            run_result["cohorts"].append(_run_cohort_flow(client, cohort_ids, index))

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"simulation_{timestamp}.json"
    md_path = output_dir / f"simulation_{timestamp}.md"
    json_path.write_text(json.dumps(run_result, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown_report(run_result), encoding="utf-8")

    print(f"Simulation complete. Residents: {args.users}, cohorts: {len(run_result['cohorts'])}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    if run_result["cohorts"]:
        first = run_result["cohorts"][0]
        print(
            f"Example cohort -> top activity: {first['top_activity_id']}, "
            f"fit: {first['top_fit_score']}, residents: {', '.join(first['resident_ids'])}"
        )


if __name__ == "__main__":
    main()
