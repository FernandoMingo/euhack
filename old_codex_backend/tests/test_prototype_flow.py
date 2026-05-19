from __future__ import annotations


def test_resident_demo_flow_locks_reveal_until_check_in(client):
    me = client.get("/api/resident/me")
    assert me.status_code == 200
    assert me.json()["id"] == "resident_sofia"

    invitations = client.get("/api/resident/invitations")
    assert invitations.status_code == 200
    invitation = invitations.json()[0]
    assert invitation["status"] == "sent"
    assert invitation["activity"]["title"] == "Calm Photography Walk"

    locked = client.get("/api/activities/activity_calm_photo_walk/circle-reveal")
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
    assert locked.json()["attendees"] == []

    accepted = client.post(f"/api/invitations/{invitation['id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    checked_in = client.post("/api/activities/activity_calm_photo_walk/check-in")
    assert checked_in.status_code == 200
    assert checked_in.json()["circle_reveal_unlocked"] is True

    reveal = client.get("/api/activities/activity_calm_photo_walk/circle-reveal")
    assert reveal.status_code == 200
    assert reveal.json()["locked"] is False
    assert {attendee["first_name"] for attendee in reveal.json()["attendees"]} == {"Leila", "Marta", "Nina", "Aya"}
    assert "email" not in reveal.json()["attendees"][0]


def test_reflection_is_persisted(client):
    response = client.post(
        "/api/activities/activity_calm_photo_walk/feedback",
        json={
            "felt_after": "calmer",
            "would_do_similar_again": "probably",
            "preference_adjustment": "keep walks under 90 minutes",
        },
    )
    assert response.status_code == 200
    assert response.json()["felt_after"] == "calmer"
    assert response.json()["preference_adjustment"] == "keep walks under 90 minutes"


def test_professional_dashboard_profile_and_preference_edit(client):
    referrals = client.get("/api/professionals/referrals")
    assert referrals.status_code == 200
    sofia = referrals.json()[0]
    assert sofia["resident"]["first_name"] == "Sofia"
    assert sofia["created_by"]["name"] == "Dr. Anna Vermeer"
    assert "diagnosis" not in sofia["resident"]

    updated = client.patch(
        "/api/residents/resident_sofia/preferences",
        json={"preferences": {"location_radius_km": 4, "availability": ["Saturday morning", "Sunday morning"]}},
    )
    assert updated.status_code == 200
    assert updated.json()["resident"]["location_radius_km"] == 4
    assert updated.json()["resident"]["availability"] == ["Saturday morning", "Sunday morning"]

    blocked = client.patch(
        "/api/residents/resident_sofia/preferences",
        json={"preferences": {"diagnosis": "not allowed"}},
    )
    assert blocked.status_code == 400


def test_operator_dashboard_and_deterministic_ai(client):
    proposals = client.get("/api/operator/proposals")
    assert proposals.status_code == 200
    proposal = proposals.json()[0]
    assert proposal["title"] == "Calm Photography Walk"
    assert proposal["human_approval_status"] == "pending_human_approval"

    graph = client.get("/api/operator/matching-graph/circle_photo_walk")
    assert graph.status_code == 200
    labels = {node["label"] for node in graph.json()["nodes"]}
    assert {"Sofia", "Resident A", "Resident B", "Resident C", "Resident D"}.issubset(labels)
    assert "photography/parks overlap" in graph.json()["compatibility_signals"]

    audit = client.get("/api/operator/audit/activity_calm_photo_walk")
    assert audit.status_code == 200
    assert len(audit.json()["items"]) >= 5
    assert any(item["label"] == "No clinical data used" for item in audit.json()["items"])

    ranking = client.post("/api/ai/rank-activities", json={"circle_id": "circle_photo_walk"})
    assert ranking.status_code == 200
    first = ranking.json()["ranked_activities"][0]
    assert first["title"] == "Calm Photography Walk"
    assert first["score"] == 94

    explanation = client.post("/api/ai/explain-match", json={"activity_id": "activity_calm_photo_walk"})
    assert explanation.status_code == 200
    assert explanation.json()["recommended_activity"] == "Calm Photography Walk"
    assert "People are not ranked by social value" in explanation.json()["guardrail"]

    approved = client.post("/api/operator/proposals/proposal_photo_walk/approve")
    assert approved.status_code == 200
    assert approved.json()["human_approval_status"] == "approved"
