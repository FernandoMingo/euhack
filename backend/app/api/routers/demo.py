"""
Demo compatibility router — frontend-friendly endpoints for the hackathon demo.
All endpoints are scoped to Sofia (resident id: sofia-001) for simplicity.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_connection

router = APIRouter(tags=["demo"])

SOFIA_ID = "sofia-001"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── GET /api/resident/me ────────────────────────────────────────────────────

@router.get("/api/resident/me")
def get_resident_me(conn: Connection = Depends(get_connection)):
    r = conn.execute("SELECT * FROM residents WHERE id = ?", (SOFIA_ID,)).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail="Demo resident not seeded")

    prefs = conn.execute(
        "SELECT preference_type, value FROM resident_preferences WHERE resident_id = ?", (SOFIA_ID,)
    ).fetchall()
    interests = [p["value"] for p in prefs if p["preference_type"] == "interest"]
    activity_prefs = [p["value"] for p in prefs if p["preference_type"] == "activity"]
    accessibility = [p["value"] for p in prefs if p["preference_type"] == "accessibility_need"]

    avail = conn.execute(
        "SELECT weekday, start_time_local, end_time_local FROM resident_availability WHERE resident_id = ?",
        (SOFIA_ID,),
    ).fetchall()
    availability = [f"{a['weekday']} {a['start_time_local']}-{a['end_time_local']}" for a in avail]

    avoid = [
        row["value"]
        for row in conn.execute(
            "SELECT value FROM resident_avoidances WHERE resident_id = ?", (SOFIA_ID,)
        ).fetchall()
    ]

    referral = conn.execute(
        """
        SELECT tp.full_name, tp.role, tp.organization
        FROM referrals ref
        JOIN trusted_professionals tp ON tp.id = ref.professional_id
        WHERE ref.resident_id = ?
        ORDER BY ref.created_at DESC LIMIT 1
        """,
        (SOFIA_ID,),
    ).fetchone()
    referred_by = referral["full_name"] if referral else None

    consent_row = conn.execute(
        "SELECT id FROM consent_records WHERE resident_id = ? AND status = 'active' LIMIT 1",
        (SOFIA_ID,),
    ).fetchone()
    consent_scopes: list[str] = []
    if consent_row:
        scopes = conn.execute(
            "SELECT scope FROM consent_scopes WHERE consent_id = ?", (consent_row["id"],)
        ).fetchall()
        consent_scopes = [s["scope"] for s in scopes]

    return {
        "id": r["id"],
        "first_name": r["first_name"],
        "email": r["email"],
        "preferred_language": r["preferred_language"],
        "city": r["city"],
        "neighborhood": r["neighborhood"],
        "approx_location": f"{r['neighborhood']}, {r['city']}",
        "location_radius_km": r["location_radius_km"],
        "social_comfort": r["social_comfort"],
        "preferred_group_size": {"min": r["preferred_group_size_min"], "max": r["preferred_group_size_max"]},
        "preferred_group_size_min": r["preferred_group_size_min"],
        "preferred_group_size_max": r["preferred_group_size_max"],
        "cost_sensitivity": r["cost_sensitivity"],
        "status": r["status"],
        "interests": interests,
        "activity_preferences": activity_prefs,
        "availability": availability,
        "accessibility_needs": accessibility,
        "avoid": avoid,
        "companion_pass_allowed": False,
        "referred_by": referred_by,
        "consent_scopes": consent_scopes,
        "locked_fields": ["first_name", "email", "city", "neighborhood", "referred_by", "consent_scopes"],
    }


# ── GET /api/resident/invitations ─────────────────────────────────────────

@router.get("/api/resident/invitations")
def get_resident_invitations(conn: Connection = Depends(get_connection)):
    rows = conn.execute(
        """
        SELECT i.id, i.status, i.companion_pass_used,
               a.id as act_id, a.title, a.activity_type, a.start_at, a.end_at,
               a.capacity, a.cost_cents, a.risk_level, a.approval_status,
               v.name as venue_name, v.address, v.lat, v.lng,
               h.full_name as host_name,
               c.shared_signals_json
        FROM invitations i
        JOIN activities a ON a.id = i.activity_id
        JOIN venues v ON v.id = a.venue_id
        LEFT JOIN hosts h ON h.id = a.host_id
        LEFT JOIN circles c ON c.id = i.circle_id
        WHERE i.resident_id = ?
        ORDER BY a.start_at
        """,
        (SOFIA_ID,),
    ).fetchall()

    result = []
    for row in rows:
        acc_tags = [
            t["accessibility_tag"]
            for t in conn.execute(
                "SELECT accessibility_tag FROM activity_accessibility WHERE activity_id = ?",
                (row["act_id"],),
            ).fetchall()
        ]
        try:
            signals = json.loads(row["shared_signals_json"] or "[]")
        except Exception:
            signals = []
        why_fit = "; ".join(signals) if signals else "Matched to your preferences"

        # Build human-readable labels
        from datetime import datetime as dt
        try:
            start = dt.fromisoformat(row["start_at"])
            date_time_label = start.strftime("%A %d %B · %H:%M")
            availability_label = start.strftime("%A morning")
        except Exception:
            date_time_label = row["start_at"]
            availability_label = ""

        cost = "Free" if row["cost_cents"] == 0 else f"€{row['cost_cents'] / 100:.2f}"

        result.append({
            "id": row["id"],
            "resident_id": SOFIA_ID,
            "activity_id": row["act_id"],
            "status": row["status"],
            "companion_pass_available": bool(row["companion_pass_used"]),
            "activity": {
                "id": row["act_id"],
                "title": row["title"],
                "activity_type": row["activity_type"],
                "date_time_label": date_time_label,
                "availability_label": availability_label,
                "location": {
                    "name": row["venue_name"],
                    "address": row["address"],
                    "lat": row["lat"] or 52.3579,
                    "lng": row["lng"] or 4.8686,
                },
                "group_size": row["capacity"],
                "pace": "calm",
                "intensity": "low",
                "host": row["host_name"] or "CivicCircles Host",
                "cost": cost,
                "cost_amount": row["cost_cents"],
                "accessibility": acc_tags,
                "alcohol_free": True,
                "tags": signals[:4] if signals else [],
                "status": row["approval_status"],
                "why_fit": why_fit,
            },
        })
    return result


# ── POST /api/activities/{activity_id}/check-in ───────────────────────────

@router.post("/api/activities/{activity_id}/check-in")
def check_in(activity_id: str, conn: Connection = Depends(get_connection)):
    existing = conn.execute(
        "SELECT id FROM attendance_events WHERE activity_id = ? AND resident_id = ?",
        (activity_id, SOFIA_ID),
    ).fetchone()
    now = _now()
    if existing:
        conn.execute(
            "UPDATE attendance_events SET attendance_status='attended', check_in_at=? WHERE id=?",
            (now, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO attendance_events (id, activity_id, resident_id, attendance_status, check_in_at)
               VALUES (?, ?, ?, 'attended', ?)""",
            (str(uuid.uuid4()), activity_id, SOFIA_ID, now),
        )
    conn.commit()
    return {"checked_in": True, "check_in_at": now}


# ── GET /api/activities/{activity_id}/circle-reveal ───────────────────────

@router.get("/api/activities/{activity_id}/circle-reveal")
def circle_reveal(activity_id: str, conn: Connection = Depends(get_connection)):
    checked = conn.execute(
        "SELECT id FROM attendance_events WHERE activity_id=? AND resident_id=? AND attendance_status='attended'",
        (activity_id, SOFIA_ID),
    ).fetchone()

    if not checked:
        return {"activity_id": activity_id, "locked": True, "attendees": []}

    # record reveal event
    conn.execute(
        """INSERT INTO circle_reveal_events (id, activity_id, resident_id, revealed_at)
           VALUES (?, ?, ?, ?)""",
        (str(uuid.uuid4()), activity_id, SOFIA_ID, _now()),
    )
    conn.commit()

    # fetch other circle members (not Sofia)
    members = conn.execute(
        """
        SELECT r.first_name
        FROM circle_members cm
        JOIN circles ci ON ci.id = cm.circle_id
        JOIN residents r ON r.id = cm.resident_id
        WHERE ci.activity_id = ? AND cm.resident_id != ?
        LIMIT 5
        """,
        (activity_id, SOFIA_ID),
    ).fetchall()

    bios = [
        "Enjoys quiet walks and local history",
        "Photographer and coffee enthusiast",
        "Loves calm mornings in the city",
        "Museum visitor and sketch artist",
        "Parks, books, and good conversations",
    ]
    starters = [
        "What's a favourite quiet spot you've found in Amsterdam?",
        "Do you have a go-to morning routine?",
        "What made you interested in this kind of activity?",
        "Is there a neighbourhood you'd love to explore?",
        "What's something small that brings you joy lately?",
    ]

    attendees = []
    for i, m in enumerate(members):
        attendees.append({
            "first_name": m["first_name"],
            "short_bio": bios[i % len(bios)],
            "conversation_starter": starters[i % len(starters)],
        })

    return {"activity_id": activity_id, "locked": False, "attendees": attendees}


# ── POST /api/activities/{activity_id}/feedback ───────────────────────────

@router.post("/api/activities/{activity_id}/feedback")
def submit_feedback(
    activity_id: str,
    payload: dict,
    conn: Connection = Depends(get_connection),
):
    felt_after = payload.get("felt_after")
    would_repeat_raw = payload.get("would_repeat") or payload.get("would_do_similar_again")
    would_repeat = 1 if str(would_repeat_raw).lower() in ("true", "yes", "1") else 0
    notes = payload.get("notes") or payload.get("preference_adjustment")
    activity_fit_raw = payload.get("activity_fit")
    activity_fit = 1 if activity_fit_raw is not None and str(activity_fit_raw).lower() in ("true", "yes", "1") else None
    group_comfort_raw = payload.get("group_comfort")
    group_comfort = 1 if group_comfort_raw is not None and str(group_comfort_raw).lower() in ("true", "yes", "1") else None
    safety_reported = 1 if payload.get("safety_reported") else 0

    existing = conn.execute(
        "SELECT id FROM resident_feedback WHERE activity_id=? AND resident_id=?",
        (activity_id, SOFIA_ID),
    ).fetchone()

    now = _now()
    if existing:
        conn.execute(
            """UPDATE resident_feedback
               SET felt_after=?, would_repeat=?, notes=?, activity_fit=?, group_comfort=?, safety_reported=?
               WHERE id=?""",
            (felt_after, would_repeat, notes, activity_fit, group_comfort, safety_reported, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO resident_feedback
               (id, activity_id, resident_id, felt_after, would_repeat, notes, activity_fit, group_comfort, safety_reported, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), activity_id, SOFIA_ID, felt_after, would_repeat, notes, activity_fit, group_comfort, safety_reported, now),
        )
    conn.commit()
    return {"saved": True}


# ── PATCH /api/residents/{resident_id}/preferences ────────────────────────

LOCKED_FIELDS = {"first_name", "email", "date_of_birth", "referred_by", "professional_id", "city", "neighborhood"}


@router.patch("/api/residents/{resident_id}/preferences")
def patch_preferences(
    resident_id: str,
    payload: dict,
    conn: Connection = Depends(get_connection),
):
    prefs = payload.get("preferences", payload)

    # strip locked fields silently
    for f in LOCKED_FIELDS:
        prefs.pop(f, None)

    now = _now()

    resident = conn.execute("SELECT id FROM residents WHERE id = ?", (resident_id,)).fetchone()
    if resident is None:
        raise HTTPException(status_code=404, detail="Resident not found")

    # scalar updates on residents table
    scalar_map = {
        "social_comfort": "social_comfort",
        "preferred_group_size_min": "preferred_group_size_min",
        "preferred_group_size_max": "preferred_group_size_max",
        "cost_sensitivity": "cost_sensitivity",
    }
    updates = {col: prefs[key] for key, col in scalar_map.items() if key in prefs}
    if updates:
        set_clause = ", ".join(f"{col}=?" for col in updates)
        vals = list(updates.values()) + [now, resident_id]
        conn.execute(f"UPDATE residents SET {set_clause}, updated_at=? WHERE id=?", vals)

    # interests
    if "interests" in prefs:
        conn.execute(
            "DELETE FROM resident_preferences WHERE resident_id=? AND preference_type='interest'",
            (resident_id,),
        )
        for v in prefs["interests"]:
            conn.execute(
                "INSERT OR IGNORE INTO resident_preferences (id, resident_id, preference_type, value, created_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), resident_id, "interest", v, now),
            )

    if "activity_preferences" in prefs:
        conn.execute(
            "DELETE FROM resident_preferences WHERE resident_id=? AND preference_type='activity'",
            (resident_id,),
        )
        for v in prefs["activity_preferences"]:
            conn.execute(
                "INSERT OR IGNORE INTO resident_preferences (id, resident_id, preference_type, value, created_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), resident_id, "activity", v, now),
            )

    if "accessibility_needs" in prefs:
        conn.execute(
            "DELETE FROM resident_preferences WHERE resident_id=? AND preference_type='accessibility_need'",
            (resident_id,),
        )
        for v in prefs["accessibility_needs"]:
            conn.execute(
                "INSERT OR IGNORE INTO resident_preferences (id, resident_id, preference_type, value, created_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), resident_id, "accessibility_need", v, now),
            )

    if "avoid" in prefs:
        conn.execute("DELETE FROM resident_avoidances WHERE resident_id=?", (resident_id,))
        for v in prefs["avoid"]:
            conn.execute(
                "INSERT OR IGNORE INTO resident_avoidances (id, resident_id, value, created_at) VALUES (?,?,?,?)",
                (str(uuid.uuid4()), resident_id, v, now),
            )

    if "availability" in prefs:
        conn.execute("DELETE FROM resident_availability WHERE resident_id=?", (resident_id,))
        for av in prefs["availability"]:
            if isinstance(av, dict):
                conn.execute(
                    "INSERT INTO resident_availability (id, resident_id, weekday, start_time_local, end_time_local, created_at) VALUES (?,?,?,?,?,?)",
                    (str(uuid.uuid4()), resident_id, av["weekday"], av["start_time_local"], av["end_time_local"], now),
                )

    conn.commit()
    return {"saved": True, "resident_id": resident_id}
