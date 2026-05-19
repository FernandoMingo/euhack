from __future__ import annotations

from app.dataclasses import ActivityTemplate, ActivityTemplateTag
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


def _row_to_template(row: object) -> ActivityTemplate:
    return ActivityTemplate(
        id=row["id"],  # type: ignore[index]
        code=row["code"],  # type: ignore[index]
        title=row["title"],  # type: ignore[index]
        description=row["description"],  # type: ignore[index]
        family=row["family"],  # type: ignore[index]
        typical_duration_minutes=row["typical_duration_minutes"],  # type: ignore[index]
        typical_group_size_min=row["typical_group_size_min"],  # type: ignore[index]
        typical_group_size_max=row["typical_group_size_max"],  # type: ignore[index]
        typical_cost_band=row["typical_cost_band"],  # type: ignore[index,arg-type]
        social_energy=row["social_energy"],  # type: ignore[index,arg-type]
        setting=row["setting"],  # type: ignore[index,arg-type]
        intensity=row["intensity"],  # type: ignore[index,arg-type]
        noise_level=row["noise_level"],  # type: ignore[index,arg-type]
        structure=row["structure"],  # type: ignore[index,arg-type]
        risk_level=row["risk_level"],  # type: ignore[index,arg-type]
        created_at=parse_dt(row["created_at"]),  # type: ignore[index,arg-type]
        updated_at=parse_dt(row["updated_at"]),  # type: ignore[index,arg-type]
    )


class ActivityTemplateRepository(RepositoryBase):
    def upsert_template(
        self,
        *,
        code: str,
        title: str,
        description: str,
        family: str,
        typical_duration_minutes: int,
        typical_group_size_min: int,
        typical_group_size_max: int,
        typical_cost_band: str,
        social_energy: str,
        setting: str,
        intensity: str,
        noise_level: str,
        structure: str,
        risk_level: str,
    ) -> ActivityTemplate:
        template_id = new_id("template")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO activity_templates (
                id, code, title, description, family,
                typical_duration_minutes, typical_group_size_min, typical_group_size_max,
                typical_cost_band, social_energy, setting, intensity, noise_level,
                structure, risk_level, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                family = excluded.family,
                typical_duration_minutes = excluded.typical_duration_minutes,
                typical_group_size_min = excluded.typical_group_size_min,
                typical_group_size_max = excluded.typical_group_size_max,
                typical_cost_band = excluded.typical_cost_band,
                social_energy = excluded.social_energy,
                setting = excluded.setting,
                intensity = excluded.intensity,
                noise_level = excluded.noise_level,
                structure = excluded.structure,
                risk_level = excluded.risk_level,
                updated_at = excluded.updated_at
            """,
            (
                template_id,
                code,
                title,
                description,
                family,
                typical_duration_minutes,
                typical_group_size_min,
                typical_group_size_max,
                typical_cost_band,
                social_energy,
                setting,
                intensity,
                noise_level,
                structure,
                risk_level,
                now,
                now,
            ),
        )
        row = self.fetchone("SELECT * FROM activity_templates WHERE code = ?", (code,))
        if row is None:
            raise RuntimeError(f"Failed to upsert template with code={code}")
        return _row_to_template(row)

    def replace_tags(self, *, template_id: str, tags: list[str]) -> list[ActivityTemplateTag]:
        self.execute("DELETE FROM activity_template_tags WHERE template_id = ?", (template_id,))
        results: list[ActivityTemplateTag] = []
        for tag in tags:
            tag_id = new_id("tpl_tag")
            self.execute(
                """
                INSERT INTO activity_template_tags (id, template_id, tag)
                VALUES (?, ?, ?)
                """,
                (tag_id, template_id, tag),
            )
            results.append(ActivityTemplateTag(id=tag_id, template_id=template_id, tag=tag))
        return results

    def get_template_by_code(self, code: str) -> ActivityTemplate | None:
        row = self.fetchone("SELECT * FROM activity_templates WHERE code = ?", (code,))
        if row is None:
            return None
        return _row_to_template(row)

    def get_tags(self, template_id: str) -> list[str]:
        rows = self.fetchall(
            "SELECT tag FROM activity_template_tags WHERE template_id = ? ORDER BY tag",
            (template_id,),
        )
        return [row["tag"] for row in rows]

    def list_templates(self, *, family: str | None = None) -> list[ActivityTemplate]:
        if family is None:
            rows = self.fetchall(
                "SELECT * FROM activity_templates ORDER BY family, title"
            )
        else:
            rows = self.fetchall(
                "SELECT * FROM activity_templates WHERE family = ? ORDER BY title",
                (family,),
            )
        return [_row_to_template(row) for row in rows]

    def count_templates(self) -> int:
        row = self.fetchone("SELECT COUNT(*) AS c FROM activity_templates")
        return int(row["c"]) if row is not None else 0

    def list_families(self) -> list[str]:
        rows = self.fetchall(
            "SELECT DISTINCT family FROM activity_templates ORDER BY family"
        )
        return [row["family"] for row in rows]

    def search_by_tag(self, tag: str) -> list[ActivityTemplate]:
        rows = self.fetchall(
            """
            SELECT t.* FROM activity_templates t
            JOIN activity_template_tags g ON g.template_id = t.id
            WHERE g.tag = ?
            ORDER BY t.title
            """,
            (tag,),
        )
        return [_row_to_template(row) for row in rows]
