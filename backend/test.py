import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.db import connect, init_db
from app.env import load_default_env_files
from app.repositories import ActivityRepository, ActivityTemplateRepository, ResidentRepository
from app.repositories.base import utc_now_iso
from app.seed import seed_activity_templates
from app.services import (
    ActivityPlanningService,
    MatchingWorkflowService,
    OpenAIChatLLMClient,
    build_email_client_from_env,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
INVITE_EMAIL = "mingomorenof@gmail.com"

load_default_env_files(start_dir=REPO_ROOT)
init_db()

with connect() as conn:
    seed_activity_templates(conn=conn)
    activities = ActivityRepository(conn)
    residents = ResidentRepository(conn)
    templates = ActivityTemplateRepository(conn)
    template = templates.get_template_by_code("pottery_making_class")
    assert template is not None

    suffix = uuid4().hex[:8]
    member_ids = []
    for idx in range(3):
        resident = residents.create_resident(
            first_name=f"Test Resident {idx}",
            email=f"test-{suffix}-{idx}@example.com",
            preferred_language="English",
            city="Rotterdam",
            social_comfort="small_group_low_pressure",
            preferred_group_size_min=3,
            preferred_group_size_max=6,
            cost_sensitivity="free_or_low_cost",
        )
        member_ids.append(resident.id)

    circle = activities.create_circle(
        template_id=template.id,
        status="proposed",
        fit_score=0.74,
        shared_signals_json=json.dumps({
            "shared_availability": ["sat_afternoon"],
            "shared_interests": [
                "interest:pottery",
                "interest:ceramics",
                "attribute:creative",
                "skill:beginner_friendly",
            ],
        }, sort_keys=True),
    )

    for resident_id in member_ids:
        activities.add_circle_member(circle_id=circle.id, resident_id=resident_id)
    conn.commit()

    service = ActivityPlanningService(conn, llm_client=OpenAIChatLLMClient())
    result = service.generate_plan_for_circle(
        circle_id=circle.id,
        operator_constraints={
            "activity_type": "beginner pottery class",
            "search_area": "Rotterdam Centrum, Noord, or Kralingen",
            "budget": "low cost if possible",
            "preferred_time_window": "Saturday afternoon",
            "venue_requirements": [
                "actual pottery or ceramics venue in Rotterdam",
                "beginner-friendly workshop or class",
                "reachable by public transport",
            ],
        },
        requested_by="local_test",
    )

    print("Plan ID:", result.plan.id)
    print("Generated pottery class activity plan:")
    print(json.dumps(result.response_content, indent=2))

    venue = activities.create_venue(
        name="Rotterdam Pottery Studio",
        address="Westersingel 45",
        city="Rotterdam",
    )
    now = datetime.now(timezone.utc)
    days_until_saturday = (5 - now.weekday()) % 7 or 7
    start_at = (now + timedelta(days=days_until_saturday)).replace(
        hour=14, minute=0, second=0, microsecond=0
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

    existing = conn.execute(
        "SELECT id FROM residents WHERE email = ?",
        (INVITE_EMAIL,),
    ).fetchone()
    if existing is not None:
        invite_resident = residents.get_resident(existing["id"])
        print(f"Reusing existing resident for {INVITE_EMAIL}")
    else:
        invite_resident = residents.create_resident(
            first_name="Fran",
            email=INVITE_EMAIL,
            preferred_language="English",
            city="Rotterdam",
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