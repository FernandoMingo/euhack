import json
from pathlib import Path
from uuid import uuid4

from app.db import connect, init_db
from app.env import load_default_env_files
from app.repositories import ActivityRepository, ActivityTemplateRepository, ResidentRepository
from app.seed import seed_activity_templates
from app.services import ActivityPlanningService, OpenAIChatLLMClient

load_default_env_files(start_dir=Path.cwd())
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