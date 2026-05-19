"""Auto-seed a companion pool + activity templates on backend startup.

The demo flow needs at least a dozen residents in the pool so the matching
engine can build a circle for any new referral. Running this at startup
makes the backend self-sufficient — the operator doesn't have to remember
to run ``seed_jose_demo.py`` first.

Idempotent: every helper uses ``INSERT OR REPLACE`` / ``IGNORE`` and
short-circuits if the templates/companions are already present.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db import connect
from app.seed import seed_activity_templates

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Companion pool — Amsterdam-leaning residents with diverse but overlapping
# interests so the matcher can almost always assemble a 3-5 person circle.
COMPANIONS: tuple[dict[str, object], ...] = (
    {
        "id": "companion-mees",
        "first_name": "Mees",
        "neighborhood": "Oud-West",
        "interests": ("theme:outdoor", "theme:urban", "attribute:creative"),
        "activities": ("photography_walk", "coffee_meetup"),
    },
    {
        "id": "companion-elif",
        "first_name": "Elif",
        "neighborhood": "De Pijp",
        "interests": ("theme:nature", "attribute:calm", "attribute:reflective"),
        "activities": ("slow_park_walk", "nature_walk_forest"),
    },
    {
        "id": "companion-bram",
        "first_name": "Bram",
        "neighborhood": "Oud-West",
        "interests": ("theme:cultural", "attribute:cultural", "attribute:reflective"),
        "activities": ("museum_visit", "library_event"),
    },
    {
        "id": "companion-noor",
        "first_name": "Noor",
        "neighborhood": "Westerpark",
        "interests": ("theme:outdoor", "attribute:creative", "attribute:expressive"),
        "activities": ("photography_walk", "slow_park_walk"),
    },
    {
        "id": "companion-pieter",
        "first_name": "Pieter",
        "neighborhood": "Oud-West",
        "interests": ("theme:cultural", "attribute:calm", "access:quiet_space"),
        "activities": ("museum_visit", "coffee_meetup"),
    },
    {
        "id": "companion-amira",
        "first_name": "Amira",
        "neighborhood": "Bos en Lommer",
        "interests": ("theme:nature", "attribute:creative", "attribute:expressive"),
        "activities": ("nature_walk_forest", "photography_walk"),
    },
    {
        "id": "companion-thijs",
        "first_name": "Thijs",
        "neighborhood": "Oud-West",
        "interests": ("theme:urban", "attribute:reflective", "access:step_free_possible"),
        "activities": ("coffee_meetup", "photography_walk"),
    },
    {
        "id": "companion-sara",
        "first_name": "Sara",
        "neighborhood": "De Baarsjes",
        "interests": ("theme:nature", "attribute:calm", "access:quiet_space"),
        "activities": ("slow_park_walk", "museum_visit"),
    },
    {
        "id": "companion-lars",
        "first_name": "Lars",
        "neighborhood": "Oud-West",
        "interests": ("theme:outdoor", "attribute:calm", "attribute:creative"),
        "activities": ("photography_walk", "nature_walk_forest"),
    },
    {
        "id": "companion-rania",
        "first_name": "Rania",
        "neighborhood": "Oud-West",
        "interests": ("theme:cultural", "attribute:cultural", "attribute:reflective"),
        "activities": ("museum_visit", "library_event"),
    },
    {
        "id": "companion-david",
        "first_name": "David",
        "neighborhood": "Centrum",
        "interests": ("attribute:calm", "access:quiet_space", "theme:cultural"),
        "activities": ("coffee_meetup", "museum_visit"),
    },
    {
        "id": "companion-fatma",
        "first_name": "Fatma",
        "neighborhood": "Oud-West",
        "interests": ("theme:outdoor", "theme:nature", "attribute:calm"),
        "activities": ("slow_park_walk", "photography_walk"),
    },
    {
        "id": "companion-jonas",
        "first_name": "Jonas",
        "neighborhood": "Westerpark",
        "interests": ("theme:urban", "attribute:creative", "attribute:expressive"),
        "activities": ("photography_walk", "coffee_meetup"),
    },
    {
        "id": "companion-iris",
        "first_name": "Iris",
        "neighborhood": "Oud-West",
        "interests": ("theme:nature", "attribute:reflective", "access:quiet_space"),
        "activities": ("nature_walk_forest", "slow_park_walk"),
    },
    {
        "id": "companion-omar",
        "first_name": "Omar",
        "neighborhood": "De Pijp",
        "interests": ("theme:cultural", "attribute:cultural", "attribute:reflective"),
        "activities": ("museum_visit", "library_event"),
    },
)


def _ensure_companion(conn: sqlite3.Connection, member: dict[str, object]) -> None:
    rid = str(member["id"])
    # civiccirclenl+<id>@gmail.com routes back to the demo sender so
    # any test invitation that ends up here never bounces externally.
    email = f"civiccirclenl+{rid}@gmail.com"
    conn.execute(
        """INSERT OR REPLACE INTO residents
           (id, first_name, email, preferred_language, city, neighborhood,
            location_radius_km, social_comfort, preferred_group_size_min,
            preferred_group_size_max, cost_sensitivity, status,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            rid,
            str(member["first_name"]),
            email,
            "English",
            "Amsterdam",
            str(member["neighborhood"]),
            5,
            "small_group_low_pressure",
            2,
            6,
            "free_or_low_cost",
            "active",
            _now(),
            _now(),
        ),
    )
    # Preferences — skip if any already exist for this companion (idempotent).
    has_prefs = conn.execute(
        "SELECT 1 FROM resident_preferences WHERE resident_id = ? LIMIT 1",
        (rid,),
    ).fetchone()
    if has_prefs is None:
        for tag in member["interests"]:  # type: ignore[union-attr]
            conn.execute(
                """INSERT OR IGNORE INTO resident_preferences
                   (id, resident_id, preference_type, value, created_at)
                   VALUES (?,?,?,?,?)""",
                (str(uuid.uuid4()), rid, "interest", str(tag), _now()),
            )
        for tag in member["activities"]:  # type: ignore[union-attr]
            conn.execute(
                """INSERT OR IGNORE INTO resident_preferences
                   (id, resident_id, preference_type, value, created_at)
                   VALUES (?,?,?,?,?)""",
                (str(uuid.uuid4()), rid, "activity", str(tag), _now()),
            )
        conn.execute(
            """INSERT OR IGNORE INTO resident_preferences
               (id, resident_id, preference_type, value, created_at)
               VALUES (?,?,?,?,?)""",
            (str(uuid.uuid4()), rid, "accessibility_need", "step_free_route", _now()),
        )
    # Availability — Saturday + Sunday mornings so referrals match the
    # canonical weekend slot the demo activities sit in.
    has_avail = conn.execute(
        "SELECT 1 FROM resident_availability WHERE resident_id = ? LIMIT 1",
        (rid,),
    ).fetchone()
    if has_avail is None:
        for weekday in ("sat", "sun"):
            conn.execute(
                """INSERT INTO resident_availability
                   (id, resident_id, weekday, start_time_local, end_time_local, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (str(uuid.uuid4()), rid, weekday, "09:00", "13:00", _now()),
            )


def ensure_demo_companions(db_path: Path | str) -> None:
    """Seed templates + companion pool. Cheap on second run."""
    with connect(db_path=db_path) as conn:
        # Required by the matcher's template ranking.
        seed_activity_templates(conn=conn)
        for member in COMPANIONS:
            _ensure_companion(conn, member)
        conn.commit()
    logger.info(
        "auto_seed.ready companions=%d templates_loaded=True",
        len(COMPANIONS),
    )
