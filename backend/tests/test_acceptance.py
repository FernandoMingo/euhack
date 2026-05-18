from __future__ import annotations


def test_resident_can_view_two_invitations_and_rsvp(client):
    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    resident_headers = {"x-actor-role": "resident", "x-actor-id": "resident_123"}

    client.post("/api/ai/generate-circles", json={}, headers=operator_headers)
    client.post(
        "/api/operator/proposals/activity_001/approve",
        json={"reason_code": "ACCEPT_FOR_DEMO"},
        headers=operator_headers,
    )
    client.post(
        "/api/operator/proposals/activity_002/approve",
        json={"reason_code": "ACCEPT_FOR_DEMO"},
        headers=operator_headers,
    )

    invitations = client.get("/api/resident/invitations", headers=resident_headers)
    assert invitations.status_code == 200
    assert len(invitations.json()["data"]) >= 2

    invitation_id = invitations.json()["data"][0]["id"]
    accept = client.post(f"/api/invitations/{invitation_id}/accept", headers=resident_headers)
    assert accept.status_code == 200
    assert accept.json()["data"]["status"] == "accepted"


def test_circle_reveal_unlocks_only_after_checkin(client):
    resident_headers = {"x-actor-role": "resident", "x-actor-id": "resident_123"}
    locked = client.get("/api/activities/activity_001/circle-reveal", headers=resident_headers)
    assert locked.status_code == 403
    checked_in = client.post("/api/activities/activity_001/check-in", headers=resident_headers)
    assert checked_in.status_code == 200
    unlocked = client.get("/api/activities/activity_001/circle-reveal", headers=resident_headers)
    assert unlocked.status_code == 200


def test_professional_can_create_referral_profile_end_to_end(client):
    professional_headers = {"x-actor-role": "professional", "x-actor-id": "professional_456"}
    referral = client.post(
        "/api/residents/referral",
        json={
            "resident_id": "resident_999",
            "first_name": "Elena",
            "email": "elena@example.com",
            "preferred_language": "English",
            "consent_given": True,
            "consent_scope": [
                "create_social_profile",
                "use_profile_for_activity_matching",
                "send_activity_invitations",
            ],
        },
        headers=professional_headers,
    )
    assert referral.status_code == 201
    profile = client.post(
        "/api/residents/resident_999/profile",
        json={
            "approx_location": {"city": "Amsterdam", "neighborhood": "Noord"},
            "location_radius_km": 4,
            "interests": ["walking"],
            "activity_preferences": ["walks"],
            "availability": ["Saturday morning"],
            "social_comfort": "small_group_low_pressure",
            "preferred_group_size": {"min": 3, "max": 5},
            "accessibility_needs": ["step_free_route"],
            "cost_sensitivity": "free_or_low_cost",
            "avoid": ["alcohol"],
            "profile_visibility": {"first_name": True},
        },
        headers=professional_headers,
    )
    assert profile.status_code == 200


def test_operator_can_approve_or_reject_ai_proposal(client):
    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    proposal = client.post(
        "/api/ai/generate-activity-proposal",
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
        headers=operator_headers,
    )
    assert proposal.status_code == 200
    proposal_id = proposal.json()["data"]["proposal_id"]
    approve = client.post(
        f"/api/operator/proposals/{proposal_id}/approve",
        json={"reason_code": "CHECKLIST_APPROVE"},
        headers=operator_headers,
    )
    assert approve.status_code == 200
    reject = client.post(
        f"/api/operator/proposals/{proposal_id}/reject",
        json={"reason_code": "CHECKLIST_REJECT"},
        headers=operator_headers,
    )
    assert reject.status_code == 200


def test_activity_ranking_explains_top_option(client):
    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    ranked = client.post(
        "/api/ai/rank-activities",
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
        headers=operator_headers,
    )
    assert ranked.status_code == 200
    first = ranked.json()["data"]["ranked_activities"][0]
    assert "component_scores" in first
    assert "fit_score" in first


def test_safety_privacy_audit_view_has_five_checks(client):
    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    audit = client.get("/api/operator/audit/activity_001", headers=operator_headers)
    assert audit.status_code == 200
    checklist = audit.json()["data"]["checklist"]
    assert len(checklist.keys()) >= 5


def test_post_event_reflection_affects_next_recommendation(client):
    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    resident_headers = {"x-actor-role": "resident", "x-actor-id": "resident_123"}
    feedback = client.post(
        "/api/activities/activity_001/feedback",
        json={
            "attended": True,
            "felt_after": "better",
            "activity_fit": "yes",
            "group_comfort": "yes",
            "would_repeat": True,
            "safety_report": False,
        },
        headers=resident_headers,
    )
    assert feedback.status_code == 201
    updated = client.post(
        "/api/ai/update-preferences-from-feedback",
        json={"resident_id": "resident_123"},
        headers=operator_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["updates"] != {}


def test_full_demo_script_runs_without_manual_improvisation(client):
    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    resident_headers = {"x-actor-role": "resident", "x-actor-id": "resident_123"}
    professional_headers = {"x-actor-role": "professional", "x-actor-id": "professional_456"}

    referrals = client.get("/api/professionals/referrals", headers=professional_headers)
    assert referrals.status_code == 200

    circles = client.post("/api/ai/generate-circles", json={}, headers=operator_headers)
    assert circles.status_code == 200
    proposal = client.post(
        "/api/ai/generate-activity-proposal",
        json={"resident_ids": ["resident_123", "resident_234", "resident_345", "resident_456", "resident_567"]},
        headers=operator_headers,
    )
    assert proposal.status_code == 200
    proposal_id = proposal.json()["data"]["proposal_id"]
    approve = client.post(
        f"/api/operator/proposals/{proposal_id}/approve",
        json={"reason_code": "DEMO_APPROVAL"},
        headers=operator_headers,
    )
    assert approve.status_code == 200
    invitations = client.get("/api/resident/invitations", headers=resident_headers)
    assert invitations.status_code == 200
    invitation_id = invitations.json()["data"][0]["id"]
    assert client.post(f"/api/invitations/{invitation_id}/accept", headers=resident_headers).status_code == 200
    assert client.post(f"/api/activities/{proposal_id}/check-in", headers=resident_headers).status_code == 200
    assert client.get(f"/api/activities/{proposal_id}/circle-reveal", headers=resident_headers).status_code == 200
