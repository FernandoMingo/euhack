"""
Demo compatibility router — frontend-friendly endpoints for the hackathon demo.
All endpoints are scoped to Sofia (resident id: sofia-001) for simplicity.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_connection

router = APIRouter(tags=["demo"])

SOFIA_ID = "sofia-001"
BACKEND_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = BACKEND_ROOT / "data" / "activity_catalog.json"

AVAILABILITY_OPTIONS = {
    "weekday_morning": ("mon", "09:00", "12:00", "Weekday morning"),
    "weekday_afternoon": ("mon", "13:00", "17:00", "Weekday afternoon"),
    "weekday_evening": ("thu", "18:00", "20:30", "Weekday evening"),
    "sat_morning": ("sat", "09:00", "13:00", "Saturday morning"),
    "sat_afternoon": ("sat", "13:00", "17:00", "Saturday afternoon"),
    "sun_morning": ("sun", "09:00", "12:00", "Sunday morning"),
    "sun_afternoon": ("sun", "13:00", "17:00", "Sunday afternoon"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label(value: str) -> str:
    cleaned = value.split(":", 1)[-1]
    return cleaned.replace("_", " ").replace("-", " ").title()


def _load_catalog() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Activity catalog missing at {CATALOG_PATH.relative_to(BACKEND_ROOT)}",
        )
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="Activity catalog must be a JSON list")
    return [item for item in data if isinstance(item, dict)]


def _option(value: str, label: str | None = None) -> dict[str, str]:
    return {"value": value, "label": label or _label(value)}


def _catalog_options() -> dict[str, list[dict[str, str]]]:
    catalog = _load_catalog()
    activity_types = sorted(
        [_option(str(item["code"]), str(item.get("title") or _label(str(item["code"])))) for item in catalog if item.get("code")],
        key=lambda item: item["label"],
    )

    interest_values: set[str] = set()
    access_values: set[str] = set()
    for item in catalog:
        family = item.get("family")
        if family:
            interest_values.add(str(family))
        setting = item.get("setting")
        if setting:
            interest_values.add(f"setting:{setting}")
        for tag in item.get("tags") or []:
            tag = str(tag)
            if tag.startswith("access:"):
                access_values.add(tag)
            else:
                interest_values.add(tag)

    accessibility: list[dict[str, str]] = []
    for tag in sorted(access_values):
        raw = tag.split(":", 1)[-1]
        value = "step_free_route" if raw == "step_free_possible" else raw
        accessibility.append(_option(value, "Step-Free Route" if value == "step_free_route" else None))

    return {
        "activity_types": activity_types,
        "interests": sorted([_option(v) for v in interest_values], key=lambda item: item["label"]),
        "accessibility_needs": accessibility,
        "social_comfort": [
            _option("one_on_one", "One-on-one"),
            _option("small_group_low_pressure", "Small group, low pressure"),
            _option("small_group", "Small group"),
            _option("larger_group", "Larger group"),
        ],
        "cost_sensitivity": [
            _option("free_or_low_cost", "Free or low cost"),
            _option("budget", "Budget"),
            _option("flexible", "Flexible"),
        ],
        "availability": [
            _option(value, label) for value, (_, _, _, label) in AVAILABILITY_OPTIONS.items()
        ],
        "avoid": [
            _option("alcohol", "Alcohol"),
            _option("loud_venues", "Loud venues"),
            _option("late_night", "Late night"),
            _option("large_groups", "Large groups"),
            _option("high_intensity", "High intensity"),
            _option("competitive_activities", "Competitive activities"),
        ],
    }


def _availability_value(weekday: str, start: str, end: str) -> str:
    for value, (day, start_time, end_time, _) in AVAILABILITY_OPTIONS.items():
        if (weekday, start, end) == (day, start_time, end_time):
            return value
    return f"{weekday}_{start}_{end}"


def _availability_row(value: Any) -> tuple[str, str, str] | None:
    if isinstance(value, dict):
        try:
            return str(value["weekday"]), str(value["start_time_local"]), str(value["end_time_local"])
        except KeyError:
            return None
    if not isinstance(value, str):
        return None
    if value in AVAILABILITY_OPTIONS:
        day, start, end, _ = AVAILABILITY_OPTIONS[value]
        return day, start, end
    parts = value.split("_")
    if len(parts) >= 3 and parts[0] in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
        return parts[0], parts[1], parts[2]
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _resident_payload(conn: Connection, resident_id: str = SOFIA_ID) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM residents WHERE id = ?", (resident_id,)).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail="Demo resident not seeded")

    prefs = conn.execute(
        "SELECT preference_type, value FROM resident_preferences WHERE resident_id = ?", (resident_id,)
    ).fetchall()
    interests = [p["value"] for p in prefs if p["preference_type"] == "interest"]
    activity_prefs = [p["value"] for p in prefs if p["preference_type"] == "activity"]
    accessibility = [p["value"] for p in prefs if p["preference_type"] == "accessibility_need"]

    avail = conn.execute(
        "SELECT weekday, start_time_local, end_time_local FROM resident_availability WHERE resident_id = ?",
        (resident_id,),
    ).fetchall()
    availability = [
        _availability_value(a["weekday"], a["start_time_local"], a["end_time_local"])
        for a in avail
    ]

    avoid = [
        row["value"]
        for row in conn.execute(
            "SELECT value FROM resident_avoidances WHERE resident_id = ?", (resident_id,)
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
        (resident_id,),
    ).fetchone()
    referred_by = referral["full_name"] if referral else None

    consent_row = conn.execute(
        "SELECT id FROM consent_records WHERE resident_id = ? AND status = 'active' LIMIT 1",
        (resident_id,),
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


def _invitation_payload(conn: Connection, row) -> dict[str, Any]:
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

    try:
        start = datetime.fromisoformat(row["start_at"])
        date_time_label = "Demo now" if row["act_id"] == "act-demo-near-me" else start.strftime("%A %d %B · %H:%M")
        availability_label = "Demo now" if row["act_id"] == "act-demo-near-me" else start.strftime("%A morning")
    except Exception:
        date_time_label = row["start_at"]
        availability_label = ""

    lat = float(row["lat"]) if row["lat"] is not None else None
    lng = float(row["lng"]) if row["lng"] is not None else None
    cost = "Free" if row["cost_cents"] == 0 else f"€{row['cost_cents'] / 100:.2f}"

    return {
        "id": row["id"],
        "resident_id": SOFIA_ID,
        "activity_id": row["act_id"],
        "status": row["status"],
        "companion_pass_available": not bool(row["companion_pass_used"]),
        "activity": {
            "id": row["act_id"],
            "title": row["title"],
            "activity_type": row["activity_type"],
            "date_time_label": date_time_label,
            "availability_label": availability_label,
            "location": {
                "name": row["venue_name"],
                "address": row["address"],
                "lat": lat,
                "lng": lng,
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
    }


def _invitation_row(conn: Connection, invitation_id: str):
    return conn.execute(
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
        WHERE i.id = ? AND i.resident_id = ?
        """,
        (invitation_id, SOFIA_ID),
    ).fetchone()


# ── GET /api/resident/me ────────────────────────────────────────────────────

@router.get("/api/resident/me")
def get_resident_me(conn: Connection = Depends(get_connection)):
    return _resident_payload(conn, SOFIA_ID)


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
          AND a.approval_status != 'rejected'
          AND (c.status IS NULL OR c.status != 'cancelled')
        ORDER BY a.start_at
        """,
        (SOFIA_ID,),
    ).fetchall()

    return [_invitation_payload(conn, row) for row in rows]


@router.get("/api/catalog/preferences")
def get_preference_catalog():
    return _catalog_options()


@router.post("/api/demo/nearby-activity")
def create_nearby_activity(payload: dict, conn: Connection = Depends(get_connection)):
    """Demo-only: pin one test activity to Sofia's initial geolocation."""
    try:
        lat = float(payload["lat"])
        lng = float(payload["lng"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="lat and lng must be numbers")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="lat/lng out of range")

    force = bool(payload.get("force", False))
    activity_id = "act-demo-near-me"
    invitation_id = "inv-sofia-act-demo-near-me"
    circle_id = "circle-demo-near-me"
    venue_id = "venue-demo-near-me"
    host_id = "host-demo-near-me"

    existing = _invitation_row(conn, invitation_id)
    if existing and not force:
        return _invitation_payload(conn, existing)

    now = _now()
    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO hosts (id, full_name, contact_email, host_type, created_at, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (host_id, "CivicCircles demo host", "demo@civiccircles.nl", "facilitator", now, now),
        )
        conn.execute(
            """INSERT OR REPLACE INTO venues (id, name, address, city, lat, lng, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (venue_id, "Your current starting point", "Initial geolocation point", "Amsterdam", lat, lng, now, now),
        )
        conn.execute(
            """INSERT OR REPLACE INTO activities
               (id, title, activity_type, venue_id, host_id, start_at, end_at,
                capacity, cost_cents, risk_level, approval_status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                activity_id,
                "Calm Check-in Test",
                "slow_park_walk",
                venue_id,
                host_id,
                now,
                now,
                4,
                0,
                "low",
                "approved",
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO activity_accessibility (id, activity_id, accessibility_tag) VALUES (?,?,?)",
            (str(uuid.uuid4()), activity_id, "step_free_route"),
        )
        conn.execute(
            """INSERT OR REPLACE INTO circles
               (id, activity_id, status, fit_score, shared_signals_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                circle_id,
                activity_id,
                "invitations_sent",
                0.95,
                json.dumps([
                    "placed at your starting location",
                    "50m check-in test",
                    "step-free route available",
                    "small group comfort",
                ]),
                now,
                now,
            ),
        )
        member_ids = [SOFIA_ID, "member-lena-001", "member-tom-002", "member-mara-003", "member-felix-004"]
        for member_id in member_ids:
            resident = conn.execute("SELECT id FROM residents WHERE id=?", (member_id,)).fetchone()
            if resident:
                conn.execute(
                    "INSERT OR IGNORE INTO circle_members (id, circle_id, resident_id, joined_at) VALUES (?,?,?,?)",
                    (str(uuid.uuid4()), circle_id, member_id, now),
                )
        conn.execute(
            """INSERT OR REPLACE INTO invitations
               (id, circle_id, activity_id, resident_id, status, companion_pass_used, sent_at)
               VALUES (?,?,?,?,?,?,?)""",
            (invitation_id, circle_id, activity_id, SOFIA_ID, "sent", 0, now),
        )

    row = _invitation_row(conn, invitation_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Nearby invitation could not be loaded")
    return _invitation_payload(conn, row)


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

LOCKED_FIELDS = {
    "first_name",
    "email",
    "date_of_birth",
    "referred_by",
    "professional_id",
    "city",
    "neighborhood",
    "consent_scopes",
    "diagnoses",
    "diagnosis",
    "therapy_notes",
    "medication_history",
    "clinical_notes",
}


@router.patch("/api/residents/{resident_id}/preferences")
def patch_preferences(
    resident_id: str,
    payload: dict,
    conn: Connection = Depends(get_connection),
):
    raw_prefs = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else payload
    if not isinstance(raw_prefs, dict):
        raise HTTPException(status_code=400, detail="Preference payload must be an object")
    prefs = dict(raw_prefs)
    for field in LOCKED_FIELDS:
        prefs.pop(field, None)

    now = _now()
    resident = conn.execute("SELECT id FROM residents WHERE id = ?", (resident_id,)).fetchone()
    if resident is None:
        raise HTTPException(status_code=404, detail="Resident not found")

    group = prefs.get("preferred_group_size")
    if isinstance(group, dict):
        if "min" in group:
            prefs["preferred_group_size_min"] = group["min"]
        if "max" in group:
            prefs["preferred_group_size_max"] = group["max"]

    scalar_map = {
        "social_comfort": "social_comfort",
        "preferred_group_size_min": "preferred_group_size_min",
        "preferred_group_size_max": "preferred_group_size_max",
        "cost_sensitivity": "cost_sensitivity",
        "location_radius_km": "location_radius_km",
    }

    def replace_preferences(key: str, preference_type: str) -> None:
        conn.execute(
            "DELETE FROM resident_preferences WHERE resident_id=? AND preference_type=?",
            (resident_id, preference_type),
        )
        for value in _as_list(prefs.get(key)):
            if value is None or value == "":
                continue
            conn.execute(
                "INSERT OR IGNORE INTO resident_preferences (id, resident_id, preference_type, value, created_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), resident_id, preference_type, str(value), now),
            )

    try:
        updates = {col: prefs[key] for key, col in scalar_map.items() if key in prefs and prefs[key] is not None}
        if updates:
            set_clause = ", ".join(f"{col}=?" for col in updates)
            vals = list(updates.values()) + [now, resident_id]
            conn.execute(f"UPDATE residents SET {set_clause}, updated_at=? WHERE id=?", vals)

        if "interests" in prefs:
            replace_preferences("interests", "interest")

        if "activity_preferences" in prefs:
            replace_preferences("activity_preferences", "activity")

        if "accessibility_needs" in prefs:
            replace_preferences("accessibility_needs", "accessibility_need")

        if "avoid" in prefs:
            conn.execute("DELETE FROM resident_avoidances WHERE resident_id=?", (resident_id,))
            for value in _as_list(prefs.get("avoid")):
                if value is None or value == "":
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO resident_avoidances (id, resident_id, value, created_at) VALUES (?,?,?,?)",
                    (str(uuid.uuid4()), resident_id, str(value), now),
                )

        if "availability" in prefs:
            conn.execute("DELETE FROM resident_availability WHERE resident_id=?", (resident_id,))
            for availability in _as_list(prefs.get("availability")):
                row = _availability_row(availability)
                if row is None:
                    continue
                weekday, start_time, end_time = row
                conn.execute(
                    "INSERT INTO resident_availability (id, resident_id, weekday, start_time_local, end_time_local, created_at) VALUES (?,?,?,?,?,?)",
                    (str(uuid.uuid4()), resident_id, weekday, start_time, end_time, now),
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {"saved": True, "resident_id": resident_id, "resident": _resident_payload(conn, resident_id)}
