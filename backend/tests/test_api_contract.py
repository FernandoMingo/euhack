from __future__ import annotations


def _assert_envelope(body: dict):
    assert set(body.keys()) == {"ok", "data", "error", "meta"}
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]


def test_success_responses_follow_contract(client, headers):
    health = client.get("/health")
    _assert_envelope(health.json())
    assert health.json()["ok"] is True
    assert health.json()["error"] is None

    me = client.get("/api/resident/me", headers=headers["resident"])
    _assert_envelope(me.json())
    assert me.json()["ok"] is True
    assert me.json()["data"]["id"] == "resident_123"


def test_error_responses_follow_contract(client):
    unauthorized = client.get("/api/resident/me")
    _assert_envelope(unauthorized.json())
    assert unauthorized.json()["ok"] is False
    assert unauthorized.json()["data"] is None
    assert unauthorized.json()["error"]["reason_code"] == "UNAUTHORIZED"


def test_request_id_header_is_propagated(client, headers):
    response = client.get(
        "/api/resident/me",
        headers={**headers["resident"], "x-request-id": "req_test_contract_123"},
    )
    body = response.json()
    assert body["meta"]["request_id"] == "req_test_contract_123"
