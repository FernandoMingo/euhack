"""Seed demo data for a *new* primary resident: Jose Maria Contreras.

Run from ``backend/``::

    python seed_jose_demo.py

What this does
--------------

* Re-seeds the canonical Sofia demo (so the existing flow still works).
* Adds Jose (``josemacontrerasp@gmail.com``) as an active resident,
  referred by the seeded GP Dr. Anna Vermeer.
* Adds 15 fake Amsterdam-Oud-West residents whose preferences,
  availability and group-size windows overlap with Jose's. These are the
  pool the matching engine and the demo circles draw from.
* Creates 5 approved activities (photo walk, museum morning, board games,
  coffee + sketch, forest walk) anchored to existing venues, each with
  its own circle containing Jose + 3-4 of the fake members.
* Creates 5 ``invitations`` rows for Jose against those activities.
* Backfills ``resident_inbox_items`` and queues ``outbound_email_messages``
  for each of Jose's invitations via ``InvitationInboxService`` — so the
  web inbox at ``/inbox`` and the Gmail email both show the invitation.

If ``SMTP_HOST``/``SMTP_USERNAME``/``SMTP_PASSWORD``/``EMAIL_FROM`` are
set in ``backend/.env``, the outbound emails will actually be delivered
to ``josemacontrerasp@gmail.com``. Otherwise the rows stay ``queued`` for
later delivery.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as a script
sys.path.insert(0, str(Path(__file__).parent))

from app.dataclasses import Invitation  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.env import load_default_env_files  # noqa: E402
from app.repositories.base import parse_dt, utc_now_iso  # noqa: E402
from app.seed import seed_activity_templates  # noqa: E402
from app.services import InvitationInboxService, build_email_client_from_env  # noqa: E402
from app.services.email_client import EmailMessagePayload  # noqa: E402

# Re-use the existing Sofia seed so both stories work.
from seed_demo import seed as seed_sofia  # noqa: E402

DB_PATH = Path(__file__).parent / "civiccircles.db"

JOSE_ID = "resident-jose-001"
JOSE_EMAIL = "josemacontrerasp@gmail.com"
PROF_ID = "prof-anna-001"  # seeded by seed_demo

# Fake companions need addresses that *don't bounce* — Gmail penalises a
# sender that fans out to invalid recipients. Plus-aliased Gmail goes back
# to the sending account with the original alias preserved in the To: line,
# so each fake "invitation" is auditable without producing a bounce.
_SINK_BASE = "civiccirclenl"  # local-part of the sending Gmail account
_SINK_DOMAIN = "gmail.com"


def _sink_email(slug: str) -> str:
    """Build a non-bouncing plus-aliased Gmail address for a fake companion."""
    return f"{_SINK_BASE}+{slug}@{_SINK_DOMAIN}"

# Fake residents — Amsterdam, mostly Oud-West, overlapping interests.
FAKE_MEMBERS: list[dict[str, object]] = [
    {
        "id": "resident-mees-002",
        "first_name": "Mees",
        "email": _sink_email("mees"),
        "neighborhood": "Oud-West",
        "interests": ["theme:outdoor", "theme:urban", "attribute:creative"],
        "activities": ["photography_walk", "coffee_meetup"],
    },
    {
        "id": "resident-elif-003",
        "first_name": "Elif",
        "email": _sink_email("elif"),
        "neighborhood": "De Pijp",
        "interests": ["theme:nature", "attribute:calm", "attribute:reflective"],
        "activities": ["slow_park_walk", "nature_walk_forest"],
    },
    {
        "id": "resident-bram-004",
        "first_name": "Bram",
        "email": _sink_email("bram"),
        "neighborhood": "Oud-West",
        "interests": ["theme:cultural", "attribute:cultural", "attribute:reflective"],
        "activities": ["museum_visit", "library_event"],
    },
    {
        "id": "resident-noor-005",
        "first_name": "Noor",
        "email": _sink_email("noor"),
        "neighborhood": "Westerpark",
        "interests": ["theme:outdoor", "attribute:creative", "attribute:expressive"],
        "activities": ["photography_walk", "slow_park_walk"],
    },
    {
        "id": "resident-pieter-006",
        "first_name": "Pieter",
        "email": _sink_email("pieter"),
        "neighborhood": "Oud-West",
        "interests": ["theme:cultural", "attribute:calm", "access:quiet_space"],
        "activities": ["museum_visit", "coffee_meetup"],
    },
    {
        "id": "resident-amira-007",
        "first_name": "Amira",
        "email": _sink_email("amira"),
        "neighborhood": "Bos en Lommer",
        "interests": ["theme:nature", "attribute:creative", "attribute:expressive"],
        "activities": ["nature_walk_forest", "photography_walk"],
    },
    {
        "id": "resident-thijs-008",
        "first_name": "Thijs",
        "email": _sink_email("thijs"),
        "neighborhood": "Oud-West",
        "interests": ["theme:urban", "attribute:reflective", "access:step_free_possible"],
        "activities": ["coffee_meetup", "photography_walk"],
    },
    {
        "id": "resident-sara-009",
        "first_name": "Sara",
        "email": _sink_email("sara"),
        "neighborhood": "De Baarsjes",
        "interests": ["theme:nature", "attribute:calm", "access:quiet_space"],
        "activities": ["slow_park_walk", "museum_visit"],
    },
    {
        "id": "resident-lars-010",
        "first_name": "Lars",
        "email": _sink_email("lars"),
        "neighborhood": "Oud-West",
        "interests": ["theme:outdoor", "attribute:calm", "attribute:creative"],
        "activities": ["photography_walk", "nature_walk_forest"],
    },
    {
        "id": "resident-rania-011",
        "first_name": "Rania",
        "email": _sink_email("rania"),
        "neighborhood": "Oud-West",
        "interests": ["theme:cultural", "attribute:cultural", "attribute:reflective"],
        "activities": ["museum_visit", "library_event"],
    },
    {
        "id": "resident-david-012",
        "first_name": "David",
        "email": _sink_email("david"),
        "neighborhood": "Centrum",
        "interests": ["attribute:calm", "access:quiet_space", "theme:cultural"],
        "activities": ["coffee_meetup", "museum_visit"],
    },
    {
        "id": "resident-fatma-013",
        "first_name": "Fatma",
        "email": _sink_email("fatma"),
        "neighborhood": "Oud-West",
        "interests": ["theme:outdoor", "theme:nature", "attribute:calm"],
        "activities": ["slow_park_walk", "photography_walk"],
    },
    {
        "id": "resident-jonas-014",
        "first_name": "Jonas",
        "email": _sink_email("jonas"),
        "neighborhood": "Westerpark",
        "interests": ["theme:urban", "attribute:creative", "attribute:expressive"],
        "activities": ["photography_walk", "coffee_meetup"],
    },
    {
        "id": "resident-iris-015",
        "first_name": "Iris",
        "email": _sink_email("iris"),
        "neighborhood": "Oud-West",
        "interests": ["theme:nature", "attribute:reflective", "access:quiet_space"],
        "activities": ["nature_walk_forest", "slow_park_walk"],
    },
    {
        "id": "resident-omar-016",
        "first_name": "Omar",
        "email": _sink_email("omar"),
        "neighborhood": "De Pijp",
        "interests": ["theme:cultural", "attribute:cultural", "attribute:reflective"],
        "activities": ["museum_visit", "library_event"],
    },
]

# 5 activities for Jose — each with its own circle composed of Jose + 3-4 fake members
JOSE_ACTIVITIES: list[dict[str, object]] = [
    {
        "id": "act-jose-photo-walk",
        "title": "Saturday Photography Walk · Vondelpark",
        "activity_type": "photography_walk",
        "venue_id": "venue-vondelpark",
        "start_offset_days": 3,
        "start_local": "10:30",
        "duration_minutes": 120,
        "capacity": 5,
        "signals": [
            "outdoor photography overlap",
            "calm pace · small group",
            "step-free route available",
            "photography interest match",
        ],
        "accessibility": ["step_free_route"],
        "member_ids": [
            "resident-mees-002",
            "resident-noor-005",
            "resident-lars-010",
            "resident-jonas-014",
        ],
    },
    {
        "id": "act-jose-museum",
        "title": "Quiet Morning at the Rijksmuseum",
        "activity_type": "museum_visit",
        "venue_id": "venue-rijksmuseum",
        "start_offset_days": 5,
        "start_local": "10:00",
        "duration_minutes": 120,
        "capacity": 4,
        "signals": [
            "cultural interest overlap",
            "calm pace",
            "small group comfort",
            "step-free route",
        ],
        "accessibility": ["step_free_route"],
        "member_ids": [
            "resident-bram-004",
            "resident-pieter-006",
            "resident-rania-011",
            "resident-omar-016",
        ],
    },
    {
        "id": "act-jose-coffee",
        "title": "Slow Coffee & Sketching",
        "activity_type": "coffee_meetup",
        "venue_id": "venue-cafe-wester",
        "start_offset_days": 6,
        "start_local": "10:30",
        "duration_minutes": 120,
        "capacity": 5,
        "signals": [
            "coffee + sketching overlap",
            "quiet atmosphere",
            "low pressure",
            "small group",
        ],
        "accessibility": [],
        "member_ids": [
            "resident-mees-002",
            "resident-thijs-008",
            "resident-david-012",
            "resident-jonas-014",
        ],
    },
    {
        "id": "act-jose-forest",
        "title": "Nature Walk · Amsterdamse Bos",
        "activity_type": "nature_walk_forest",
        "venue_id": "venue-vondelpark",  # nearest existing venue for the demo
        "start_offset_days": 7,
        "start_local": "09:30",
        "duration_minutes": 150,
        "capacity": 6,
        "signals": [
            "nature interest overlap",
            "calm pace",
            "step-free route",
            "guided walk",
        ],
        "accessibility": ["step_free_route"],
        "member_ids": [
            "resident-elif-003",
            "resident-amira-007",
            "resident-fatma-013",
            "resident-iris-015",
        ],
    },
    {
        "id": "act-jose-boardgames",
        "title": "Calm Board Games Evening",
        "activity_type": "social",
        "venue_id": "venue-community",
        "start_offset_days": 9,
        "start_local": "18:30",
        "duration_minutes": 120,
        "capacity": 5,
        "signals": [
            "low-pressure social",
            "alcohol-free",
            "small group",
            "community space",
        ],
        "accessibility": [],
        "member_ids": [
            "resident-sara-009",
            "resident-david-012",
            "resident-pieter-006",
            "resident-rania-011",
        ],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _start_at(days_ahead: int, hhmm: str) -> str:
    base = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date()
    hh, mm = (int(p) for p in hhmm.split(":"))
    when = datetime(base.year, base.month, base.day, hh, mm, tzinfo=timezone.utc)
    return when.isoformat()


def _end_at(start_iso: str, duration_minutes: int) -> str:
    return (datetime.fromisoformat(start_iso) + timedelta(minutes=duration_minutes)).isoformat()


def _insert_resident(
    conn: sqlite3.Connection,
    *,
    rid: str,
    first_name: str,
    email: str,
    neighborhood: str = "Oud-West",
    social_comfort: str = "small_group_low_pressure",
    group_min: int = 3,
    group_max: int = 6,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO residents
           (id, first_name, email, preferred_language, city, neighborhood,
            location_radius_km, social_comfort, preferred_group_size_min,
            preferred_group_size_max, cost_sensitivity, status,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            rid,
            first_name,
            email,
            "English",
            "Amsterdam",
            neighborhood,
            5,
            social_comfort,
            group_min,
            group_max,
            "free_or_low_cost",
            "active",
            _now(),
            _now(),
        ),
    )


def _add_preferences(
    conn: sqlite3.Connection,
    *,
    rid: str,
    interests: list[str],
    activities: list[str],
    accessibility: list[str] | None = None,
) -> None:
    for ptype, values in [
        ("interest", interests),
        ("activity", activities),
        ("accessibility_need", accessibility or []),
    ]:
        conn.execute(
            "DELETE FROM resident_preferences WHERE resident_id=? AND preference_type=?",
            (rid, ptype),
        )
        for v in values:
            conn.execute(
                """INSERT OR IGNORE INTO resident_preferences
                   (id, resident_id, preference_type, value, created_at)
                   VALUES (?,?,?,?,?)""",
                (str(uuid.uuid4()), rid, ptype, v, _now()),
            )


def _add_availability(
    conn: sqlite3.Connection,
    *,
    rid: str,
    windows: list[tuple[str, str, str]],
) -> None:
    conn.execute("DELETE FROM resident_availability WHERE resident_id=?", (rid,))
    for weekday, start, end in windows:
        conn.execute(
            """INSERT INTO resident_availability
               (id, resident_id, weekday, start_time_local, end_time_local, created_at)
               VALUES (?,?,?,?,?,?)""",
            (str(uuid.uuid4()), rid, weekday, start, end, _now()),
        )


def _add_avoidances(conn: sqlite3.Connection, *, rid: str, values: list[str]) -> None:
    conn.execute("DELETE FROM resident_avoidances WHERE resident_id=?", (rid,))
    for v in values:
        conn.execute(
            """INSERT OR IGNORE INTO resident_avoidances
               (id, resident_id, value, created_at) VALUES (?,?,?,?)""",
            (str(uuid.uuid4()), rid, v, _now()),
        )


def _add_referral_and_consent(
    conn: sqlite3.Connection,
    *,
    rid: str,
    referral_id: str,
    consent_id: str,
    referral_reason: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO referrals
           (id, resident_id, professional_id, referral_reason, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (referral_id, rid, PROF_ID, referral_reason, "accepted", _now()),
    )
    conn.execute(
        """INSERT OR REPLACE INTO consent_records
           (id, resident_id, professional_id, status, granted_at, created_at)
           VALUES (?,?,?,?,?,?)""",
        (consent_id, rid, PROF_ID, "active", _now(), _now()),
    )
    for scope in [
        "create_social_profile",
        "use_profile_for_activity_matching",
        "send_activity_invitations",
        "share_limited_status_with_professional",
    ]:
        conn.execute(
            "INSERT OR IGNORE INTO consent_scopes (id, consent_id, scope) VALUES (?,?,?)",
            (str(uuid.uuid4()), consent_id, scope),
        )


def flush_queued_emails(db_path: Path = DB_PATH) -> int:
    """Re-attempt delivery for every ``outbound_email_messages`` row still 'queued'.

    Reads SMTP / Resend env vars (``.env`` is auto-loaded) and uses whatever
    email client that returns. Updates each row in place: 'sent' on success,
    'failed' with ``error_message`` on failure.

    Returns the number of rows that successfully transitioned to 'sent'.
    """
    load_default_env_files()
    email_client = build_email_client_from_env()
    if email_client is None:
        print(
            "No email client configured. Set SMTP_HOST / SMTP_USERNAME / "
            "SMTP_PASSWORD / EMAIL_FROM (Gmail) or RESEND_API_KEY + "
            "EMAIL_FROM in backend/.env and re-run with --flush."
        )
        return 0

    provider = getattr(email_client, "provider_name", "unknown")
    print(f"Flushing queued emails via provider={provider} ...")

    sent_count = 0
    failed_count = 0
    with connect(db_path=db_path) as conn:
        # Retry both rows we never tried yet (queued) and rows the provider
        # rejected on a previous attempt (failed). Gmail's 5.7.14 / rate-limit
        # blocks clear after the user signs into the web account, so the same
        # row will go through on the next try.
        rows = conn.execute(
            """
            SELECT id, resident_id, to_email, subject, body
              FROM outbound_email_messages
             WHERE delivery_status IN ('queued', 'failed')
             ORDER BY created_at
            """
        ).fetchall()
        for row in rows:
            payload = EmailMessagePayload(
                to_email=row["to_email"],
                subject=row["subject"],
                body=row["body"],
                resident_id=row["resident_id"],
            )
            try:
                result = email_client.send(payload)
            except Exception as exc:  # pragma: no cover - defensive
                conn.execute(
                    """UPDATE outbound_email_messages
                          SET delivery_status='failed',
                              provider=?,
                              error_message=?,
                              updated_at=?
                        WHERE id=?""",
                    (provider, f"{type(exc).__name__}: {exc}", utc_now_iso(), row["id"]),
                )
                failed_count += 1
                continue
            new_status = result.status
            if new_status == "sent":
                conn.execute(
                    """UPDATE outbound_email_messages
                          SET delivery_status='sent',
                              provider=?,
                              provider_message_id=?,
                              error_message=NULL,
                              sent_at=?,
                              updated_at=?
                        WHERE id=?""",
                    (
                        result.provider,
                        result.provider_message_id,
                        utc_now_iso(),
                        utc_now_iso(),
                        row["id"],
                    ),
                )
                sent_count += 1
                print(f"  ✓ sent to {row['to_email']:<35} subject='{row['subject'][:40]}'")
            else:
                conn.execute(
                    """UPDATE outbound_email_messages
                          SET delivery_status=?,
                              provider=?,
                              error_message=?,
                              updated_at=?
                        WHERE id=?""",
                    (
                        new_status,
                        result.provider,
                        result.error_message,
                        utc_now_iso(),
                        row["id"],
                    ),
                )
                failed_count += 1
                print(
                    f"  ✗ {new_status} for {row['to_email']:<35} "
                    f"err={result.error_message}"
                )
        conn.commit()

    print(f"Flushed: sent={sent_count} failed={failed_count}")
    return sent_count


def seed(db_path: Path = DB_PATH) -> None:
    # Make sure schema + Sofia + Anna + venues + templates exist first.
    init_db(db_path=db_path)
    seed_sofia(db_path=db_path)

    # Activity-template catalog drives the matching engine's ranking; without
    # it no template ever passes constraints. Idempotent on re-seed.
    with connect(db_path=db_path) as conn_t:
        seed_activity_templates(conn=conn_t)
        conn_t.commit()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    # ── Jose ────────────────────────────────────────────────────────────────
    _insert_resident(
        conn,
        rid=JOSE_ID,
        first_name="Jose",
        email=JOSE_EMAIL,
        neighborhood="Oud-West",
        group_min=3,
        group_max=6,
    )
    _add_preferences(
        conn,
        rid=JOSE_ID,
        interests=[
            "theme:outdoor",
            "theme:nature",
            "theme:urban",
            "theme:cultural",
            "attribute:calm",
            "attribute:creative",
            "attribute:reflective",
            "access:quiet_space",
        ],
        activities=[
            "photography_walk",
            "slow_park_walk",
            "museum_visit",
            "coffee_meetup",
            "nature_walk_forest",
        ],
        accessibility=["step_free_route"],
    )
    _add_availability(
        conn,
        rid=JOSE_ID,
        windows=[
            ("sat", "09:00", "13:00"),
            ("sun", "09:00", "13:00"),
            ("wed", "18:00", "21:00"),
        ],
    )
    _add_avoidances(conn, rid=JOSE_ID, values=["alcohol", "loud_venues"])
    _add_referral_and_consent(
        conn,
        rid=JOSE_ID,
        referral_id="ref-jose-anna",
        consent_id="consent-jose-001",
        referral_reason=(
            "Recently moved to Amsterdam, wants to meet people in calm small-group "
            "settings around photography, walks, and museums."
        ),
    )

    # ── 15 fake companions ──────────────────────────────────────────────────
    for member in FAKE_MEMBERS:
        _insert_resident(
            conn,
            rid=str(member["id"]),
            first_name=str(member["first_name"]),
            email=str(member["email"]),
            neighborhood=str(member["neighborhood"]),
            group_min=2,
            group_max=6,
        )
        _add_preferences(
            conn,
            rid=str(member["id"]),
            interests=list(member["interests"]),  # type: ignore[arg-type]
            activities=list(member["activities"]),  # type: ignore[arg-type]
            accessibility=["step_free_route"],
        )
        _add_availability(
            conn,
            rid=str(member["id"]),
            windows=[("sat", "09:00", "13:00"), ("sun", "10:00", "14:00")],
        )
        _add_avoidances(conn, rid=str(member["id"]), values=["alcohol"])

    # ── Activities + circles + invitations for Jose ─────────────────────────
    HOST_ID = "host-mara-001"  # seeded by seed_demo

    for spec in JOSE_ACTIVITIES:
        act_id = str(spec["id"])
        start = _start_at(int(spec["start_offset_days"]), str(spec["start_local"]))
        end = _end_at(start, int(spec["duration_minutes"]))

        conn.execute(
            """INSERT OR REPLACE INTO activities
               (id, title, activity_type, venue_id, host_id, start_at, end_at,
                capacity, cost_cents, risk_level, approval_status,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                act_id,
                str(spec["title"]),
                str(spec["activity_type"]),
                str(spec["venue_id"]),
                HOST_ID,
                start,
                end,
                int(spec["capacity"]),
                0,
                "low",
                "approved",
                _now(),
                _now(),
            ),
        )
        for tag in list(spec["accessibility"]):  # type: ignore[arg-type]
            conn.execute(
                """INSERT OR IGNORE INTO activity_accessibility
                   (id, activity_id, accessibility_tag) VALUES (?,?,?)""",
                (str(uuid.uuid4()), act_id, tag),
            )

        circle_id = f"circle-{act_id}"
        conn.execute(
            """INSERT OR REPLACE INTO circles
               (id, activity_id, status, fit_score, shared_signals_json,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                circle_id,
                act_id,
                "invitations_sent",
                0.91,
                json.dumps({
                    "shared_interests": list(spec["signals"])[:3],  # type: ignore[arg-type]
                    "shared_availability": ["Saturday morning"],
                }),
                _now(),
                _now(),
            ),
        )

        member_ids = [JOSE_ID] + list(spec["member_ids"])  # type: ignore[arg-type]
        for mid in member_ids:
            conn.execute(
                """INSERT OR IGNORE INTO circle_members
                   (id, circle_id, resident_id, joined_at) VALUES (?,?,?,?)""",
                (str(uuid.uuid4()), circle_id, mid, _now()),
            )

        conn.execute(
            """INSERT OR REPLACE INTO invitations
               (id, circle_id, activity_id, resident_id, status,
                companion_pass_used, sent_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                f"inv-jose-{act_id}",
                circle_id,
                act_id,
                JOSE_ID,
                "sent",
                0,
                _now(),
            ),
        )

    conn.commit()
    conn.close()

    # ── Inbox items + outbound emails for Jose ──────────────────────────────
    # Done after the main commit so InvitationInboxService sees the rows.
    # If SMTP / Resend env vars are set, the service dispatches the emails
    # immediately at creation time. Otherwise rows are persisted as 'queued'
    # and can be flushed later via --flush.
    load_default_env_files()
    email_client = build_email_client_from_env()
    with connect(db_path=db_path) as conn2:
        service = InvitationInboxService(conn2, email_client=email_client)
        rows = conn2.execute(
            "SELECT * FROM invitations WHERE resident_id = ?", (JOSE_ID,)
        ).fetchall()
        for row in rows:
            already = conn2.execute(
                "SELECT 1 FROM resident_inbox_items WHERE invitation_id = ?",
                (row["id"],),
            ).fetchone()
            if already:
                continue
            inv = Invitation(
                id=row["id"],
                circle_id=row["circle_id"],
                activity_id=row["activity_id"],
                resident_id=row["resident_id"],
                status=row["status"],
                companion_pass_used=bool(row["companion_pass_used"]),
                sent_at=parse_dt(row["sent_at"]),  # type: ignore[arg-type]
                responded_at=parse_dt(row["responded_at"])
                if row["responded_at"]
                else None,
            )
            service.create_artifacts_for_invitation(invitation=inv)
        conn2.commit()

    print(
        "Seeded Jose ({email}) with {n_acts} invitations and {n_friends} "
        "potential companions.".format(
            email=JOSE_EMAIL,
            n_acts=len(JOSE_ACTIVITIES),
            n_friends=len(FAKE_MEMBERS),
        )
    )
    smtp_set = all(
        os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM")
    )
    if smtp_set:
        print("SMTP env vars detected -> outbound emails queued and will deliver.")
    else:
        print(
            "SMTP env vars NOT set -> outbound_email_messages rows stay queued.\n"
            "  Configure SMTP_HOST=smtp.gmail.com, SMTP_USERNAME=<gmail>, "
            "SMTP_PASSWORD=<gmail app password>, EMAIL_FROM=<from@gmail.com> "
            "in backend/.env to actually deliver to Gmail."
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed Jose demo + optionally flush emails.")
    parser.add_argument(
        "--flush",
        action="store_true",
        help="Skip seeding; just re-attempt delivery of any queued outbound emails.",
    )
    parser.add_argument(
        "--also-flush",
        action="store_true",
        help="Seed Jose, then immediately flush the freshly queued emails through SMTP.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help=f"Path to the SQLite DB (default: {DB_PATH}).",
    )
    args = parser.parse_args()

    if args.flush:
        flush_queued_emails(db_path=args.db_path)
    else:
        seed(db_path=args.db_path)
        if args.also_flush:
            flush_queued_emails(db_path=args.db_path)
