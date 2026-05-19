"""Single-circle invite for Jose — mirrors backend/test.py exactly.

Run from ``backend/``::

    python invite_jose.py

Builds one circle (Jose + 3 fake companions), generates a real activity
plan via OpenAI, anchors it to an approved activity, then calls
``MatchingWorkflowService.send_invitations_for_approved_circle`` so the
invitation goes out through the configured SMTP client. Prints the
SMTP-level delivery status row for the email destined for Jose so we
can tell if Gmail accepted (``status=sent``) or refused.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.db import connect, init_db
from app.env import load_default_env_files
from app.repositories import (
    ActivityRepository,
    ActivityTemplateRepository,
    ResidentRepository,
)
from app.repositories.base import utc_now_iso
from app.seed import seed_activity_templates
from app.services import (
    ActivityPlanningService,
    MatchingWorkflowService,
    OpenAIChatLLMClient,
    build_email_client_from_env,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
INVITE_EMAIL = "josemacontrerasp@gmail.com"

load_default_env_files(start_dir=REPO_ROOT)
load_default_env_files(start_dir=Path(__file__).resolve().parent)
init_db()


def main() -> None:
    with connect() as conn:
        seed_activity_templates(conn=conn)
        activities = ActivityRepository(conn)
        residents = ResidentRepository(conn)
        templates = ActivityTemplateRepository(conn)

        template = templates.get_template_by_code("photography_walk")
        assert template is not None, "photography_walk template missing"

        suffix = uuid4().hex[:8]

        # Plus-aliased Gmail so bounces don't accumulate on civiccirclenl@gmail.com
        member_ids: list[str] = []
        for idx, name in enumerate(["Mees", "Noor", "Lars"]):
            resident = residents.create_resident(
                first_name=f"{name} ({suffix})",
                email=f"civiccirclenl+companion-{suffix}-{idx}@gmail.com",
                preferred_language="English",
                city="Amsterdam",
                social_comfort="small_group_low_pressure",
                preferred_group_size_min=3,
                preferred_group_size_max=6,
                cost_sensitivity="free_or_low_cost",
            )
            member_ids.append(resident.id)

        circle = activities.create_circle(
            template_id=template.id,
            status="proposed",
            fit_score=0.91,
            shared_signals_json=json.dumps(
                {
                    "shared_availability": ["sat_morning"],
                    "shared_interests": [
                        "theme:outdoor",
                        "theme:urban",
                        "attribute:creative",
                        "attribute:calm",
                    ],
                },
                sort_keys=True,
            ),
        )

        for rid in member_ids:
            activities.add_circle_member(circle_id=circle.id, resident_id=rid)
        conn.commit()

        service = ActivityPlanningService(conn, llm_client=OpenAIChatLLMClient())
        result = service.generate_plan_for_circle(
            circle_id=circle.id,
            operator_constraints={
                "activity_type": "calm small-group photography walk",
                "search_area": "Amsterdam Vondelpark / Oud-West",
                "budget": "free",
                "preferred_time_window": "Saturday morning",
                "venue_requirements": [
                    "outdoor park or canal route",
                    "step-free, reachable by public transport",
                    "no alcohol involved",
                ],
            },
            requested_by="local_test",
        )

        print("Plan ID:", result.plan.id)
        print("Generated photography walk plan:")
        print(json.dumps(result.response_content, indent=2))

        venue = activities.create_venue(
            name="Vondelpark Photography Meet-up Point",
            address="Vondelpark Entrance, 1071 AA Amsterdam",
            city="Amsterdam",
            lat=52.3579,
            lng=4.8686,
        )
        now = datetime.now(timezone.utc)
        days_until_saturday = (5 - now.weekday()) % 7 or 7
        start_at = (now + timedelta(days=days_until_saturday)).replace(
            hour=10, minute=30, second=0, microsecond=0
        )
        end_at = start_at + timedelta(minutes=template.typical_duration_minutes)
        activity_title = template.title
        if isinstance(result.response_content, dict):
            activity_title = (
                result.response_content.get("title")
                or result.response_content.get("activity_title")
                or activity_title
            )

        activity = activities.create_activity(
            title=activity_title,
            activity_type=template.code,
            venue_id=venue.id,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            capacity=template.typical_group_size_max,
            risk_level=template.risk_level,
            approval_status="approved",
        )
        conn.execute(
            "UPDATE circles SET activity_id = ?, updated_at = ? WHERE id = ?",
            (activity.id, utc_now_iso(), circle.id),
        )

        # Look up or create Jose with the live INVITE_EMAIL.
        existing = conn.execute(
            "SELECT id FROM residents WHERE email = ?",
            (INVITE_EMAIL,),
        ).fetchone()
        if existing is not None:
            invite_resident = residents.get_resident(existing["id"])
            print(f"Reusing existing resident for {INVITE_EMAIL}")
        else:
            invite_resident = residents.create_resident(
                first_name="Jose",
                email=INVITE_EMAIL,
                preferred_language="English",
                city="Amsterdam",
                social_comfort="small_group_low_pressure",
                preferred_group_size_min=3,
                preferred_group_size_max=6,
                cost_sensitivity="free_or_low_cost",
            )
        assert invite_resident is not None

        member_ids_in_circle = {
            m.resident_id
            for m in activities.list_circle_members(circle_id=circle.id)
        }
        if invite_resident.id not in member_ids_in_circle:
            activities.add_circle_member(
                circle_id=circle.id, resident_id=invite_resident.id
            )
        conn.commit()

        email_client = build_email_client_from_env()
        if email_client is None:
            print(
                "Warning: SMTP/Resend not configured in .env; "
                "invitation emails will be queued only."
            )
        else:
            print(
                f"Email client = {getattr(email_client, 'provider_name', 'unknown')}"
            )

        workflow = MatchingWorkflowService(conn, email_client=email_client)
        invitations = workflow.send_invitations_for_approved_circle(
            circle_id=circle.id,
            actor_id="local_test",
        )
        print(f"Sent {len(invitations)} invitation(s) for circle {circle.id}")

        email_row = conn.execute(
            """
            SELECT delivery_status, provider, provider_message_id, error_message
            FROM outbound_email_messages
            WHERE resident_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (invite_resident.id,),
        ).fetchone()
        if email_row is None:
            print(f"No outbound email row found for {INVITE_EMAIL}")
        else:
            print(f"Email to {INVITE_EMAIL}:")
            print(f"  status: {email_row['delivery_status']}")
            print(f"  provider: {email_row['provider']}")
            if email_row["provider_message_id"]:
                print(f"  provider_message_id: {email_row['provider_message_id']}")
            if email_row["error_message"]:
                print(f"  error: {email_row['error_message']}")


if __name__ == "__main__":
    main()
