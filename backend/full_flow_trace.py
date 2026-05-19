"""End-to-end walkthrough: GP signs in -> Jose referral -> matchmaking -> approve -> Jose sees invitation."""
import json
import os
import sqlite3
import subprocess
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
JOSE_EMAIL = "josemacontrerasp@gmail.com"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


def step(n, label):
    print(f"\n========== Step {n}: {label} ==========")


# Step 0 — clean slate: companions exist via seed_jose_demo, but no Jose-specific data
step(0, "Reset state — seed companions, then drop Jose so GP creates him live")
subprocess.run(
    ["py", "-3.12", "seed_jose_demo.py"],
    check=True,
    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    stdout=subprocess.DEVNULL,
)
conn = sqlite3.connect("civiccircles.db")
for sql in [
    "DELETE FROM outbound_email_messages WHERE resident_id='resident-jose-001'",
    "DELETE FROM resident_inbox_items   WHERE resident_id='resident-jose-001'",
    "DELETE FROM invitations            WHERE id LIKE 'inv-jose-%'",
    "DELETE FROM circle_members         WHERE circle_id LIKE 'circle-act-jose-%'",
    "DELETE FROM circles                WHERE id LIKE 'circle-act-jose-%'",
    "DELETE FROM activity_accessibility WHERE activity_id LIKE 'act-jose-%'",
    "DELETE FROM activities             WHERE id LIKE 'act-jose-%'",
    "DELETE FROM consent_scopes         WHERE consent_id='consent-jose-001'",
    "DELETE FROM consent_records        WHERE id='consent-jose-001'",
    "DELETE FROM referrals              WHERE id='ref-jose-anna'",
    "DELETE FROM resident_preferences   WHERE resident_id='resident-jose-001'",
    "DELETE FROM resident_availability  WHERE resident_id='resident-jose-001'",
    "DELETE FROM resident_avoidances    WHERE resident_id='resident-jose-001'",
    "DELETE FROM residents              WHERE id='resident-jose-001'",
]:
    conn.execute(sql)
conn.commit()
n_pool = conn.execute(
    "SELECT COUNT(*) FROM residents WHERE id LIKE 'resident-%-0%'"
).fetchone()[0]
n_jose = conn.execute(
    "SELECT COUNT(*) FROM residents WHERE email=?", (JOSE_EMAIL,)
).fetchone()[0]
print(f"  companions in pool: {n_pool}")
print(f"  Jose in DB before GP flow: {n_jose} (expected 0)")
conn.close()

# Step 1 — GP exists already (seeded). Frontend's flow is /staff/professional → POST signup.
step(1, "GP signs in — seeded Anna (prof-anna-001) is approved")
s, anna = call("GET", "/api/professionals/prof-anna-001")
print(f"  GET /api/professionals/prof-anna-001 -> {s}")
print(f"    {anna['full_name']}  role={anna['role']}  status={anna['verification_status']}")
print("  (UI flow: GP opens /staff/professional, fills AGB/BIG form;")
print("   POST /api/professionals/signup is idempotent and auto-verifies in <100ms.)")

# Step 2 — GP creates referral for Jose with consent (Track B in /staff/professional)
step(2, "GP submits Jose's referral + consent")
s, ref = call(
    "POST",
    "/api/referrals",
    {
        "professional_id": "prof-anna-001",
        "profile": {
            "first_name": "Jose",
            "email": JOSE_EMAIL,
            "preferred_language": "English",
            "city": "Amsterdam",
            "social_comfort": "small_group_low_pressure",
            "preferred_group_size_min": 3,
            "preferred_group_size_max": 6,
            "cost_sensitivity": "free_or_low_cost",
            "neighborhood": "Oud-West",
            "interests": ["photography", "parks", "museums", "nature", "coffee"],
            "accessibility_needs": ["Step-free route"],
            "avoidances": ["alcohol", "loud_venues"],
            "availability": [
                {"weekday": "sat", "start_time_local": "09:00", "end_time_local": "13:00"},
                {"weekday": "sun", "start_time_local": "09:00", "end_time_local": "13:00"},
            ],
        },
        "capture_method": "in_consult",
        "referral_reason": "Newcomer to Amsterdam, wants small-group photography walks",
    },
)
print(f"  POST /api/referrals -> {s}")
jose_id = ref["resident"]["id"]
ref_id = ref["referral"]["id"]
print(f"  resident_id={jose_id}")
print(f"  resident.email={ref['resident']['email']}  status={ref['resident']['status']}")
print(f"  consent.scopes={ref['consent']['scopes']}")
print(f"  consent.text_version={ref['consent']['consent_text_version']}")
print(f"  referral.status={ref['referral']['status']}")

# Step 3 — Jose can now log in via /login
step(3, "Jose logs in via /login (email -> resident_id resolution)")
s, login = call("POST", "/api/residents/login", {"email": JOSE_EMAIL})
print(
    f"  POST /api/residents/login -> {s}  first_name={login.get('first_name')}  "
    f"id_matches={login.get('id') == jose_id}"
)

# Step 4 — Operator inbox shows pending referral
step(4, "Operator inbox shows the pending referral")
s, op_inbox = call("GET", "/api/demo/operator/inbox")
pending = op_inbox.get("pending_referrals", [])
print(f"  GET /api/demo/operator/inbox -> {s}  pending={len(pending)}")
for r in pending:
    print(
        f"    - referral_id={r['referral_id']}  resident={r['resident']['first_name']}  "
        f"by {r['professional']['full_name']}"
    )

# Step 5 — orchestrate: deterministic matchmaking
step(5, "Operator orchestrate — matchmaking engine + activity creation")
s, prop = call("POST", f"/api/demo/operator/referrals/{ref_id}/orchestrate", {})
if s != 200:
    print(f"  -> {s}  detail={prop.get('detail')}")
    raise SystemExit(1)
print(f"  POST /api/demo/operator/referrals/{ref_id}/orchestrate -> {s}")
print("  Matching engine selected this circle:")
print(f"      circle_id     = {prop['circle_id']}")
print(f"      template      = {prop['template_code']}  ({prop['template_title']})")
print(f"      activity      = {prop['activity']['title']}")
print(f"      start_at      = {prop['activity']['start_at']}")
print(f"      venue         = {prop['activity']['venue']['name']}")
print(f"      fit_score     = {prop['fit_score']}")
print(
    f"      circle members= {len(prop['members'])} "
    f"({', '.join(m['first_name'] for m in prop['members'])})"
)
print(f"      shared_signals= {prop['shared_interests']}")

# Step 6 — operator approves
step(6, "Operator approves -> invitations created, inbox + email dispatched")
s, invs = call("POST", f"/api/demo/operator/circles/{prop['circle_id']}/approve", {})
print(
    f"  POST /api/demo/operator/circles/{prop['circle_id']}/approve -> {s}  "
    f"invitations={len(invs)}"
)

# Step 7 — emails out via SMTP
step(7, "Outbound email rows for Jose")
conn = sqlite3.connect("civiccircles.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT delivery_status, provider, sent_at, to_email, subject
    FROM outbound_email_messages WHERE resident_id=? ORDER BY created_at DESC
    """,
    (jose_id,),
).fetchall()
for r in rows:
    print(f"  {r['delivery_status']:6} via {r['provider']:6}  to={r['to_email']}")
    print(f"      subject: {r['subject']}")
    print(f"      sent_at: {r['sent_at']}")
conn.close()

# Step 8 — Jose sees the invitation in /inbox and on /
step(8, "Jose sees the invitation in the web app")
s, rich = call("GET", f"/api/demo/residents/{jose_id}/invitations")
print(f"  GET .../invitations (rich, used by map) -> {s}  count={len(rich.get('invitations', []))}")
for inv in rich.get("invitations", []):
    a = inv["activity"]
    print(
        f"    - {a['title']:<48} @ {a['venue']['name']:<28} members={len(inv['members'])}"
    )

s, items = call("GET", f"/api/demo/residents/{jose_id}/inbox")
print(f"  GET .../inbox (privacy-safe, used by /inbox) -> {s}  items={len(items)}")
for it in items:
    print(f"    - {it['title']:<55} status={it['status']}")

print("\n========== DONE ==========")
