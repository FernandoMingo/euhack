from __future__ import annotations

import argparse

from sqlmodel import Session, select

from app.db import create_db_and_tables, engine, reset_db
from app.models import Activity, AuditItem, Circle, CircleMember, Invitation, Professional, Proposal, Resident


CONSENT_SCOPES = [
    "create_lightweight_social_profile",
    "use_profile_for_activity_matching",
    "send_activity_invitations",
    "share_limited_activity_status_with_referring_professional",
    "unlock_limited_attendee_cards_after_check_in",
]


def _merge(session: Session, item) -> None:
    session.merge(item)


def seed_demo_data(session: Session) -> None:
    professional = Professional(
        id="professional_anna",
        name="Dr. Anna Vermeer",
        role="GP",
        organization="Oud-West Health Center",
        city="Amsterdam",
        verification_status="approved",
        email="anna.vermeer@example.com",
    )
    _merge(session, professional)

    residents = [
        Resident(
            id="resident_sofia",
            first_name="Sofia",
            email="sofia@example.com",
            preferred_language="English",
            approx_location="Amsterdam, Oud-West",
            location_radius_km=3,
            location_lat=52.3602,
            location_lng=4.8645,
            interests=["photography", "parks", "coffee", "museums"],
            activity_preferences=["walks", "museum visits", "quiet cafes"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["alcohol", "loud venues", "late night"],
            companion_pass_allowed=True,
            status="active",
            consent_scopes=CONSENT_SCOPES,
            created_by_professional_id="professional_anna",
            short_bio="Enjoys noticing small details on quiet city walks.",
            conversation_starter="Ask about a favorite photo from a park.",
        ),
        Resident(
            id="resident_a",
            first_name="Leila",
            email="leila@example.com",
            preferred_language="English",
            approx_location="Amsterdam, De Pijp",
            location_radius_km=4,
            location_lat=52.3545,
            location_lng=4.8916,
            interests=["photography", "parks", "coffee"],
            activity_preferences=["walks", "quiet cafes"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["late night"],
            companion_pass_allowed=True,
            status="active",
            consent_scopes=CONSENT_SCOPES,
            created_by_professional_id="professional_anna",
            short_bio="Likes gentle walks and taking photos of street corners.",
            conversation_starter="Ask about light, shadows, or favorite coffee nearby.",
        ),
        Resident(
            id="resident_b",
            first_name="Marta",
            email="marta@example.com",
            preferred_language="English",
            approx_location="Amsterdam, Centrum",
            location_radius_km=5,
            location_lat=52.3738,
            location_lng=4.8910,
            interests=["parks", "museums", "coffee"],
            activity_preferences=["walks", "museum visits"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["alcohol"],
            companion_pass_allowed=False,
            status="active",
            consent_scopes=CONSENT_SCOPES,
            created_by_professional_id="professional_anna",
            short_bio="Usually spots quiet corners and benches first.",
            conversation_starter="Ask about a museum room that feels calm.",
        ),
        Resident(
            id="resident_c",
            first_name="Nina",
            email="nina@example.com",
            preferred_language="Dutch",
            approx_location="Amsterdam, West",
            location_radius_km=5,
            location_lat=52.3672,
            location_lng=4.8478,
            interests=["photography", "museums", "parks"],
            activity_preferences=["walks", "museum visits"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["loud venues"],
            companion_pass_allowed=True,
            status="active",
            consent_scopes=CONSENT_SCOPES,
            created_by_professional_id="professional_anna",
            short_bio="Keeps walks unhurried and likes old trees.",
            conversation_starter="Ask about a favorite tree or canal view.",
        ),
        Resident(
            id="resident_d",
            first_name="Aya",
            email="aya@example.com",
            preferred_language="English",
            approx_location="Amsterdam, Oost",
            location_radius_km=6,
            location_lat=52.3600,
            location_lng=4.9390,
            interests=["parks", "photography", "community"],
            activity_preferences=["walks", "gardening"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["alcohol"],
            companion_pass_allowed=True,
            status="active",
            consent_scopes=CONSENT_SCOPES,
            created_by_professional_id="professional_anna",
            short_bio="Enjoys slow routes and noticing seasonal changes.",
            conversation_starter="Ask about a favorite quiet place in Amsterdam.",
        ),
    ]
    for resident in residents:
        _merge(session, resident)

    activities = [
        Activity(
            id="activity_calm_photo_walk",
            title="Calm Photography Walk",
            activity_type="photography_walk",
            date_time_label="Saturday 10:30",
            availability_label="Saturday morning",
            location_name="Vondelpark",
            address="Vondelpark, Amsterdam",
            lat=52.3579,
            lng=4.8686,
            group_size=5,
            pace="calm",
            intensity="low",
            host="Mara, CivicCircles host",
            cost_label="free",
            cost_amount=0,
            accessibility=["step_free_route"],
            alcohol_free=True,
            tags=["photography", "parks", "walks", "outdoor", "calm"],
            status="proposed",
            why_fit="Sofia likes photography and parks, prefers Saturday mornings, and asked for small low-pressure groups.",
        ),
        Activity(
            id="activity_museum_morning",
            title="Quiet Museum Morning",
            activity_type="museum_visit",
            date_time_label="Saturday 11:00",
            availability_label="Saturday morning",
            location_name="Rijksmuseum",
            address="Museumstraat 1, Amsterdam",
            lat=52.3599,
            lng=4.8852,
            group_size=6,
            pace="calm",
            intensity="low",
            host="Jules, museum volunteer",
            cost_label="low cost",
            cost_amount=8,
            accessibility=["step_free_route"],
            alcohol_free=True,
            tags=["museums", "art", "quiet", "indoor"],
            status="candidate",
            why_fit="Good museum overlap, but less outdoor and photography fit.",
        ),
        Activity(
            id="activity_evening_games",
            title="Evening Board Games",
            activity_type="board_games",
            date_time_label="Saturday 20:30",
            availability_label="Saturday evening",
            location_name="Community Room West",
            address="Kinkerstraat, Amsterdam",
            lat=52.3653,
            lng=4.8668,
            group_size=8,
            pace="lively",
            intensity="medium",
            host="Sam, community host",
            cost_label="low cost",
            cost_amount=5,
            accessibility=["step_free_route"],
            alcohol_free=False,
            tags=["games", "indoor", "late night", "loud venue"],
            status="candidate",
            why_fit="Ranked lower because it is later, larger, and not alcohol-free.",
        ),
    ]
    for activity in activities:
        _merge(session, activity)

    _merge(
        session,
        Circle(
            id="circle_photo_walk",
            activity_id="activity_calm_photo_walk",
            status="forming",
            compatibility_signals=[
                "shared Saturday morning availability",
                "calm outdoor preference",
                "photography/parks overlap",
                "small group comfort",
                "step-free route requirement satisfied",
                "alcohol-free preference respected",
            ],
        ),
    )

    members = [
        ("resident_sofia", "Sofia", "Sofia"),
        ("resident_a", "Resident A", "Leila"),
        ("resident_b", "Resident B", "Marta"),
        ("resident_c", "Resident C", "Nina"),
        ("resident_d", "Resident D", "Aya"),
    ]
    resident_lookup = {resident.id: resident for resident in residents}
    for resident_id, anonymous_label, reveal_name in members:
        resident = resident_lookup[resident_id]
        _merge(
            session,
            CircleMember(
                id=f"member_photo_walk_{resident_id}",
                circle_id="circle_photo_walk",
                resident_id=resident_id,
                anonymous_label=anonymous_label,
                reveal_first_name=reveal_name,
                short_bio=resident.short_bio,
                conversation_starter=resident.conversation_starter,
                consent_reveal=True,
                checked_in=False,
            ),
        )

    _merge(
        session,
        Invitation(
            id="invitation_sofia_photo_walk",
            resident_id="resident_sofia",
            activity_id="activity_calm_photo_walk",
            status="sent",
            companion_pass_available=True,
        ),
    )

    _merge(
        session,
        Proposal(
            id="proposal_photo_walk",
            activity_id="activity_calm_photo_walk",
            title="Calm Photography Walk",
            status="proposed",
            generated_summary="Create a small, step-free Saturday photography walk in Vondelpark for residents who prefer calm outdoor activities.",
            human_approval_status="pending_human_approval",
            ranking_score=94,
            alternative_notes={
                "activity_museum_morning": "Good quiet fit, but weaker parks/outdoor signal.",
                "activity_evening_games": "Lower fit: evening time, larger group, alcohol-free preference not respected.",
            },
        ),
    )

    audit_items = [
        ("audit_consent", "Consent scopes recorded", "passed", "Sofia consented to lightweight profile, matching, invitations, and reveal after check-in."),
        ("audit_no_clinical", "No clinical data used", "passed", "No diagnoses, therapy notes, medication history, or clinical records are stored."),
        ("audit_no_people_browse", "No public attendee browsing", "passed", "Attendee cards stay locked until simulated check-in."),
        ("audit_accessibility", "Accessibility constraint checked", "passed", "Step-free route requirement is satisfied."),
        ("audit_alcohol", "Avoid list respected", "passed", "Alcohol-free preference respected for proposed activity."),
        ("audit_human", "Human approval required", "pending", "Operator must approve or reject before final activity state changes."),
    ]
    for item_id, label, status, detail in audit_items:
        _merge(
            session,
            AuditItem(
                id=item_id,
                activity_id="activity_calm_photo_walk",
                label=label,
                status=status,
                detail=detail,
            ),
        )

    session.commit()


def seed_database(reset: bool = False) -> None:
    if reset:
        reset_db()
    else:
        create_db_and_tables()
    with Session(engine) as session:
        seed_demo_data(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CivicCircles demo data")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate SQLite tables before seeding")
    args = parser.parse_args()
    seed_database(reset=args.reset)
    with Session(engine) as session:
        residents = session.exec(select(Resident)).all()
        activities = session.exec(select(Activity)).all()
    print(f"Seeded {len(residents)} residents and {len(activities)} activities.")


if __name__ == "__main__":
    main()
