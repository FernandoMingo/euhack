"""
Seed the CivicCircles demo dataset for the hackathon.
Run from backend/: python seed_demo.py
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "civiccircles.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Disable FKs during seed so INSERT OR REPLACE doesn't cascade-delete children
    conn.execute("PRAGMA foreign_keys = OFF")

    # Demo-only near-me activity is created from browser geolocation at runtime.
    # Remove any previous smoke-test/browser-created copy so a fresh seed does
    # not pin check-in testing to an old machine location.
    conn.execute("DELETE FROM attendance_events WHERE activity_id='act-demo-near-me'")
    conn.execute("DELETE FROM circle_reveal_events WHERE activity_id='act-demo-near-me'")
    conn.execute("DELETE FROM activity_accessibility WHERE activity_id='act-demo-near-me'")
    conn.execute("DELETE FROM circle_members WHERE circle_id='circle-demo-near-me'")
    conn.execute("DELETE FROM invitations WHERE id='inv-sofia-act-demo-near-me'")
    conn.execute("DELETE FROM circles WHERE id='circle-demo-near-me'")
    conn.execute("DELETE FROM activities WHERE id='act-demo-near-me'")
    conn.execute("DELETE FROM venues WHERE id='venue-demo-near-me'")
    conn.execute("DELETE FROM hosts WHERE id='host-demo-near-me'")

    # ── Trusted professional ────────────────────────────────────────────────
    PROF_ID = "prof-anna-001"
    conn.execute(
        """INSERT OR REPLACE INTO trusted_professionals
           (id, full_name, role, organization, city, email, verification_status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (PROF_ID, "Dr. Anna Vermeer", "GP", "Oud-West Health Center", "Amsterdam",
         "anna.vermeer@example.com", "approved", _now(), _now()),
    )

    # ── Sofia resident ──────────────────────────────────────────────────────
    SOFIA_ID = "sofia-001"
    conn.execute(
        """INSERT OR REPLACE INTO residents
           (id, first_name, email, preferred_language, city, neighborhood,
            location_radius_km, social_comfort, preferred_group_size_min,
            preferred_group_size_max, cost_sensitivity, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (SOFIA_ID, "Sofia", "sofia@example.com", "English", "Amsterdam", "Oud-West",
         3, "small_group_low_pressure", 3, 6, "free_or_low_cost", "active", _now(), _now()),
    )

    # preferences
    for ptype, values in [
        (
            "interest",
            [
                "theme:outdoor",
                "theme:nature",
                "attribute:calm",
                "attribute:creative",
                "attribute:cultural",
                "access:quiet_space",
            ],
        ),
        ("activity", ["photography_walk", "slow_park_walk", "museum_visit", "coffee_meetup"]),
        ("accessibility_need", ["step_free_route"]),
    ]:
        conn.execute(
            "DELETE FROM resident_preferences WHERE resident_id=? AND preference_type=?",
            (SOFIA_ID, ptype),
        )
        for v in values:
            conn.execute(
                "INSERT OR IGNORE INTO resident_preferences (id, resident_id, preference_type, value, created_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), SOFIA_ID, ptype, v, _now()),
            )

    # availability
    conn.execute("DELETE FROM resident_availability WHERE resident_id=?", (SOFIA_ID,))
    conn.execute(
        "INSERT INTO resident_availability (id, resident_id, weekday, start_time_local, end_time_local, created_at) VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), SOFIA_ID, "sat", "09:00", "13:00", _now()),
    )

    # avoidances
    conn.execute("DELETE FROM resident_avoidances WHERE resident_id=?", (SOFIA_ID,))
    for v in ["alcohol", "loud_venues", "late_night"]:
        conn.execute(
            "INSERT OR IGNORE INTO resident_avoidances (id, resident_id, value, created_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), SOFIA_ID, v, _now()),
        )

    # referral
    conn.execute(
        """INSERT OR REPLACE INTO referrals
           (id, resident_id, professional_id, referral_reason, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        ("ref-sofia-anna", SOFIA_ID, PROF_ID,
         "Social isolation — gentle reintegration", "accepted", _now()),
    )

    # consent
    CONSENT_ID = "consent-sofia-001"
    conn.execute(
        """INSERT OR REPLACE INTO consent_records
           (id, resident_id, professional_id, status, granted_at, created_at)
           VALUES (?,?,?,?,?,?)""",
        (CONSENT_ID, SOFIA_ID, PROF_ID, "active", _now(), _now()),
    )
    for scope in [
        "create_social_profile",
        "use_profile_for_activity_matching",
        "send_activity_invitations",
        "share_limited_status_with_professional",
    ]:
        conn.execute(
            "INSERT OR IGNORE INTO consent_scopes (id, consent_id, scope) VALUES (?,?,?)",
            (str(uuid.uuid4()), CONSENT_ID, scope),
        )

    # ── Demo circle members ─────────────────────────────────────────────────
    demo_members = [
        ("member-lena-001", "Lena"),
        ("member-tom-002", "Tom"),
        ("member-mara-003", "Mara"),
        ("member-felix-004", "Felix"),
    ]
    for mid, fname in demo_members:
        conn.execute(
            """INSERT OR REPLACE INTO residents
               (id, first_name, email, preferred_language, city, neighborhood,
                location_radius_km, social_comfort, preferred_group_size_min,
                preferred_group_size_max, cost_sensitivity, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, fname, f"{fname.lower()}@demo.example", "English", "Amsterdam",
             "Oud-West", 3, "small_group_low_pressure", 2, 6, "free_or_low_cost",
             "active", _now(), _now()),
        )

    # ── Host ───────────────────────────────────────────────────────────────
    HOST_ID = "host-mara-001"
    conn.execute(
        """INSERT OR REPLACE INTO hosts (id, full_name, contact_email, host_type, created_at, updated_at)
           VALUES (?,?,?,?,?,?)""",
        (HOST_ID, "Mara (CivicCircles Host)", "mara@civiccircles.nl", "volunteer", _now(), _now()),
    )

    # ── Venues ─────────────────────────────────────────────────────────────
    venues = [
        ("venue-vondelpark",   "Vondelpark Entrance",   "Vondelpark, Amsterdam",              52.3579, 4.8686),
        ("venue-rijksmuseum",  "Rijksmuseum Garden",    "Museumstraat 1, 1071 XX Amsterdam",  52.3600, 4.8852),
        ("venue-community",    "OBA Community Space",   "Oosterdokskade 143, 1011 DL Amsterdam", 52.3774, 4.9009),
        ("venue-cafe-wester",  "Café De Wester",        "Westerstraat 120, 1015 MN Amsterdam", 52.3755, 4.8831),
    ]
    for vid, name, addr, lat, lng in venues:
        conn.execute(
            """INSERT OR REPLACE INTO venues (id, name, address, city, lat, lng, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (vid, name, addr, "Amsterdam", lat, lng, _now(), _now()),
        )

    # ── Activities, circles, invitations ───────────────────────────────────
    activities_data = [
        (
            "act-photo-walk", "Calm Photography Walk", "walk", "venue-vondelpark",
            "2026-05-30T10:30:00+02:00", "2026-05-30T12:30:00+02:00", 5,
            ["shared Saturday morning availability", "calm setting", "small group comfort",
             "step-free route available", "alcohol-free", "photography overlap"],
            ["step_free_route"],
        ),
        (
            "act-museum-morning", "Quiet Museum Morning", "museum", "venue-rijksmuseum",
            "2026-05-30T10:00:00+02:00", "2026-05-30T12:00:00+02:00", 4,
            ["museum interest overlap", "calm setting", "step-free route", "small group comfort"],
            ["step_free_route"],
        ),
        (
            "act-board-games", "Evening Board Games", "social", "venue-community",
            "2026-05-30T18:00:00+02:00", "2026-05-30T20:00:00+02:00", 5,
            ["low-pressure social", "alcohol-free", "small group", "community space"],
            [],
        ),
        (
            "act-coffee-sketch", "Slow Coffee & Sketching", "social", "venue-cafe-wester",
            "2026-05-30T10:00:00+02:00", "2026-05-30T12:00:00+02:00", 4,
            ["coffee interest overlap", "calm setting", "small group", "quiet atmosphere", "sketching"],
            [],
        ),
    ]

    for act_id, title, atype, venue_id, start, end, cap, signals, acc_tags in activities_data:
        conn.execute(
            """INSERT OR REPLACE INTO activities
               (id, title, activity_type, venue_id, host_id, start_at, end_at,
                capacity, cost_cents, risk_level, approval_status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (act_id, title, atype, venue_id, HOST_ID, start, end, cap,
             0, "low", "approved", _now(), _now()),
        )
        for tag in acc_tags:
            conn.execute(
                "INSERT OR IGNORE INTO activity_accessibility (id, activity_id, accessibility_tag) VALUES (?,?,?)",
                (str(uuid.uuid4()), act_id, tag),
            )

        circle_id = f"circle-{act_id}"
        conn.execute(
            """INSERT OR REPLACE INTO circles
               (id, activity_id, status, fit_score, shared_signals_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (circle_id, act_id, "invitations_sent", 0.88,
             json.dumps(signals), _now(), _now()),
        )

        # Sofia + demo members in circle
        all_members = [SOFIA_ID] + [m[0] for m in demo_members]
        for mid in all_members:
            conn.execute(
                "INSERT OR IGNORE INTO circle_members (id, circle_id, resident_id, joined_at) VALUES (?,?,?,?)",
                (str(uuid.uuid4()), circle_id, mid, _now()),
            )

        # invitation for Sofia
        conn.execute(
            """INSERT OR REPLACE INTO invitations
               (id, circle_id, activity_id, resident_id, status, companion_pass_used, sent_at)
               VALUES (?,?,?,?,?,?,?)""",
            (f"inv-sofia-{act_id}", circle_id, act_id, SOFIA_ID, "sent", 0, _now()),
        )

    conn.commit()
    conn.close()
    print("✓ Demo data seeded successfully")


if __name__ == "__main__":
    seed()
