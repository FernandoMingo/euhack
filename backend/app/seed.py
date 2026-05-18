from __future__ import annotations

import json
import logging
from pathlib import Path
from sqlite3 import Connection

from app.repositories.activity_template_repository import ActivityTemplateRepository

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "activity_catalog.json"

logger = logging.getLogger(__name__)


def load_activity_catalog(path: Path | str = DEFAULT_CATALOG_PATH) -> list[dict[str, object]]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Activity catalog not found at {catalog_path}")
    with catalog_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("Activity catalog must be a JSON list of objects")
    return data


def seed_activity_templates(
    conn: Connection,
    catalog: list[dict[str, object]] | None = None,
    catalog_path: Path | str = DEFAULT_CATALOG_PATH,
) -> int:
    """Insert or update activity templates from the catalog.

    Returns the number of templates upserted.
    """

    if catalog is None:
        catalog = load_activity_catalog(catalog_path)

    repo = ActivityTemplateRepository(conn)
    logger.info("Seeding %d activity templates", len(catalog))

    for entry in catalog:
        template = repo.upsert_template(
            code=str(entry["code"]),
            title=str(entry["title"]),
            description=str(entry["description"]),
            family=str(entry["family"]),
            typical_duration_minutes=int(entry["typical_duration_minutes"]),
            typical_group_size_min=int(entry["typical_group_size_min"]),
            typical_group_size_max=int(entry["typical_group_size_max"]),
            typical_cost_band=str(entry["typical_cost_band"]),
            social_energy=str(entry["social_energy"]),
            setting=str(entry["setting"]),
            intensity=str(entry["intensity"]),
            noise_level=str(entry["noise_level"]),
            structure=str(entry["structure"]),
            risk_level=str(entry["risk_level"]),
        )
        tags = entry.get("tags") or []
        if not isinstance(tags, list):
            raise ValueError(f"Tags must be a list for code={entry.get('code')}")
        repo.replace_tags(template_id=template.id, tags=[str(t) for t in tags])

    conn.commit()
    count = repo.count_templates()
    logger.info("Seeded activity templates. Total in database: %d", count)
    return count
