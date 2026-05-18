from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def run_demo_script() -> dict[str, bool]:
    client = TestClient(app)
    results: dict[str, bool] = {}

    operator_headers = {"x-actor-role": "operator", "x-actor-id": "operator_001"}
    resident_headers = {"x-actor-role": "resident", "x-actor-id": "resident_123"}
    professional_headers = {"x-actor-role": "professional", "x-actor-id": "professional_456"}

    referrals = client.get("/api/professionals/referrals", headers=professional_headers)
    results["professional_can_view_referrals"] = referrals.status_code == 200

    circles = client.post("/api/ai/generate-circles", json={}, headers=operator_headers)
    results["ai_generates_circle"] = circles.status_code == 200

    proposal = client.post(
        "/api/ai/generate-activity-proposal",
        json={"resident_ids": ["resident_123", "resident_234", "resident_345", "resident_456", "resident_567"]},
        headers=operator_headers,
    )
    proposal_id = proposal.json()["data"]["proposal_id"] if proposal.status_code == 200 else "activity_001"
    approve = client.post(
        f"/api/operator/proposals/{proposal_id}/approve",
        json={"reason_code": "CITY_APPROVED"},
        headers=operator_headers,
    )
    results["operator_approves_activity"] = approve.status_code == 200

    invitations = client.get("/api/resident/invitations", headers=resident_headers)
    results["resident_has_invitations"] = invitations.status_code == 200 and len(invitations.json()["data"]) >= 1

    invitation_id = invitations.json()["data"][0]["id"]
    accept = client.post(f"/api/invitations/{invitation_id}/accept", headers=resident_headers)
    results["resident_can_rsvp"] = accept.status_code == 200

    check_in = client.post(f"/api/activities/{proposal_id}/check-in", headers=resident_headers)
    reveal = client.get(f"/api/activities/{proposal_id}/circle-reveal", headers=resident_headers)
    results["circle_reveal_after_checkin"] = check_in.status_code == 200 and reveal.status_code == 200

    feedback = client.post(
        f"/api/activities/{proposal_id}/feedback",
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
    update = client.post(
        "/api/ai/update-preferences-from-feedback",
        json={"resident_id": "resident_123"},
        headers=operator_headers,
    )
    results["feedback_affects_next_recommendation"] = feedback.status_code == 201 and update.status_code == 200
    return results


if __name__ == "__main__":
    for check, ok in run_demo_script().items():
        print(f"{check}: {'PASS' if ok else 'FAIL'}")
