from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import Activity, Circle, ConsentRecord, Professional, Resident


def _existing(session: Session, model, item_id: str) -> bool:
    return session.get(model, item_id) is not None


def seed_demo_data(session: Session) -> None:
    professional = Professional(
        id="professional_456",
        name="Dr. Anna Vermeer",
        role="GP",
        organization="Oud-West Health Center",
        verification_status="approved",
        city="Amsterdam",
        email="anna@example.com",
    )
    if not _existing(session, Professional, professional.id):
        session.add(professional)

    residents = [
        Resident(
            id="resident_123",
            first_name="Sofia",
            email="sofia@example.com",
            preferred_language="English",
            approx_location={"city": "Amsterdam", "neighborhood": "Oud-West", "lat": 52.3602, "lng": 4.8645},
            location_radius_km=3,
            interests=["photography", "parks", "coffee", "museums"],
            activity_preferences=["walks", "museum visits", "quiet cafes"],
            availability=["Saturday morning", "Sunday afternoon"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["alcohol", "loud venues", "late night"],
            profile_visibility={"photo": True, "first_name": True, "short_bio": True, "conversation_starter": True},
            status="active",
        ),
        Resident(
            id="resident_234",
            first_name="Leila",
            email="leila@example.com",
            preferred_language="English",
            approx_location={"city": "Amsterdam", "neighborhood": "De Pijp", "lat": 52.3545, "lng": 4.8916},
            location_radius_km=4,
            interests=["photography", "parks", "community"],
            activity_preferences=["walks", "volunteering"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["late night"],
            status="active",
        ),
        Resident(
            id="resident_345",
            first_name="Marta",
            email="marta@example.com",
            preferred_language="English",
            approx_location={"city": "Amsterdam", "neighborhood": "Centrum", "lat": 52.3738, "lng": 4.8910},
            location_radius_km=5,
            interests=["parks", "coffee", "art"],
            activity_preferences=["museum visits", "coffee meetups"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["alcohol"],
            status="active",
        ),
        Resident(
            id="resident_456",
            first_name="Nina",
            email="nina@example.com",
            preferred_language="Dutch",
            approx_location={"city": "Amsterdam", "neighborhood": "West", "lat": 52.3672, "lng": 4.8478},
            location_radius_km=5,
            interests=["photography", "museums", "coffee"],
            activity_preferences=["walks", "museum visits"],
            availability=["Saturday morning", "Sunday afternoon"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["loud venues"],
            status="active",
        ),
        Resident(
            id="resident_567",
            first_name="Aya",
            email="aya@example.com",
            preferred_language="English",
            approx_location={"city": "Amsterdam", "neighborhood": "Oost", "lat": 52.3600, "lng": 4.9390},
            location_radius_km=6,
            interests=["parks", "community", "photography"],
            activity_preferences=["walks", "gardening"],
            availability=["Saturday morning"],
            social_comfort="small_group_low_pressure",
            preferred_group_size={"min": 3, "max": 6},
            accessibility_needs=["step_free_route"],
            cost_sensitivity="free_or_low_cost",
            avoid=["alcohol"],
            status="active",
        ),
    ]
    for resident in residents:
        if not _existing(session, Resident, resident.id):
            session.add(resident)
        consent_id = f"consent_{resident.id.split('_')[-1]}"
        if not _existing(session, ConsentRecord, consent_id):
            session.add(
                ConsentRecord(
                    id=consent_id,
                    resident_id=resident.id,
                    professional_id="professional_456",
                    consent_scope=[
                        "create_social_profile",
                        "use_profile_for_activity_matching",
                        "send_activity_invitations",
                        "share_limited_status_with_professional",
                    ],
                )
            )

    activities = [
        Activity(
            id="activity_001",
            title="Calm Photography Walk",
            type="photography_walk",
            location={"name": "Vondelpark Entrance", "address": "Vondelpark, Amsterdam", "lat": 52.3579, "lng": 4.8686},
            start_time=datetime.fromisoformat("2026-05-23T10:30:00+02:00"),
            end_time=datetime.fromisoformat("2026-05-23T12:00:00+02:00"),
            capacity=6,
            host_id="host_001",
            cost=0,
            accessibility=["step_free_route"],
            risk_level="low",
            approval_status="generated",
            lifecycle_status="generated",
        ),
        Activity(
            id="activity_002",
            title="Museum Morning",
            type="museum_visit",
            location={"name": "Rijksmuseum", "address": "Museumstraat 1", "lat": 52.3599, "lng": 4.8852},
            start_time=datetime.fromisoformat("2026-05-23T11:00:00+02:00"),
            end_time=datetime.fromisoformat("2026-05-23T13:00:00+02:00"),
            capacity=6,
            host_id="host_002",
            cost=8,
            accessibility=["step_free_route"],
            risk_level="low",
            approval_status="generated",
            lifecycle_status="generated",
        ),
    ]
    for activity in activities:
        if not _existing(session, Activity, activity.id):
            session.add(activity)

    if not _existing(session, Circle, "circle_012"):
        session.add(
            Circle(
                id="circle_012",
                activity_id="activity_001",
                participant_ids=["resident_123", "resident_234", "resident_345", "resident_456", "resident_567"],
                shared_signals=["photography", "parks", "coffee", "small_group"],
                fit_score=0.92,
                status="generated",
            )
        )

    session.commit()
