from __future__ import annotations

from sqlmodel import Session

from app.db import engine
from app.models import Activity, Invitation


def test_operator_approval_moves_activity_and_sends_invitations(client, headers):
    generated = client.post(
        "/api/ai/generate-circles",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
    )
    assert generated.status_code == 200
    proposal_id = generated.json()["data"]["activity_id"]
    approve = client.post(
        f"/api/operator/proposals/{proposal_id}/approve",
        headers=headers["operator"],
        json={"reason_code": "STATE_TEST_APPROVE"},
    )
    assert approve.status_code == 200
    with Session(engine) as session:
        activity = session.get(Activity, proposal_id)
        assert activity is not None
        assert activity.approval_status == "approved"
        invitation = session.get(Invitation, f"invite_{proposal_id}_resident_123")
        assert invitation is not None
        assert invitation.status == "sent"


def test_invitation_accept_decline_and_companion_pass_transitions(client, headers):
    client.post(
        "/api/operator/proposals/activity_001/approve",
        headers=headers["operator"],
        json={"reason_code": "STATE_TEST_APPROVE"},
    )
    invitations = client.get("/api/resident/invitations", headers=headers["resident"])
    assert invitations.status_code == 200
    invitation_id = invitations.json()["data"][0]["id"]

    accepted = client.post(f"/api/invitations/{invitation_id}/accept", headers=headers["resident"])
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "accepted"

    declined = client.post(f"/api/invitations/{invitation_id}/decline", headers=headers["resident"])
    assert declined.status_code == 200
    assert declined.json()["data"]["status"] == "declined"

    pass_response = client.post(
        f"/api/invitations/{invitation_id}/companion-pass",
        headers=headers["resident"],
        json={"guest_name": "Trusted Friend"},
    )
    assert pass_response.status_code == 200
    assert pass_response.json()["data"]["companion_pass_used"] is True


def test_feedback_escalation_levels(client, headers):
    level3 = client.post(
        "/api/activities/activity_001/feedback",
        headers=headers["resident"],
        json={
            "attended": True,
            "felt_after": "worse",
            "activity_fit": "no",
            "group_comfort": "no",
            "would_repeat": False,
            "safety_report": True,
            "report_type": "harassment",
        },
    )
    assert level3.status_code == 201
    assert level3.json()["data"]["escalation_level"] == "level_3"

    level4 = client.post(
        "/api/activities/activity_001/feedback",
        headers=headers["resident"],
        json={
            "attended": True,
            "felt_after": "worse",
            "activity_fit": "no",
            "group_comfort": "no",
            "would_repeat": False,
            "safety_report": True,
            "report_type": "medical_or_urgent_concern",
        },
    )
    assert level4.status_code == 201
    assert level4.json()["data"]["escalation_level"] == "level_4"
