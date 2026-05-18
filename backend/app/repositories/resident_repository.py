from __future__ import annotations

from app.dataclasses import (
    Resident,
    ResidentAvailability,
    ResidentAvoidance,
    ResidentPreference,
    ResidentStatus,
)
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


class ResidentRepository(RepositoryBase):
    def create_resident(
        self,
        *,
        first_name: str,
        email: str,
        preferred_language: str,
        city: str,
        social_comfort: str,
        preferred_group_size_min: int,
        preferred_group_size_max: int,
        cost_sensitivity: str,
        neighborhood: str | None = None,
        location_radius_km: int = 3,
        status: ResidentStatus = "active",
    ) -> Resident:
        resident_id = new_id("resident")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO residents (
                id, first_name, email, preferred_language, city, neighborhood,
                location_radius_km, social_comfort, preferred_group_size_min,
                preferred_group_size_max, cost_sensitivity, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resident_id,
                first_name,
                email,
                preferred_language,
                city,
                neighborhood,
                location_radius_km,
                social_comfort,
                preferred_group_size_min,
                preferred_group_size_max,
                cost_sensitivity,
                status,
                now,
                now,
            ),
        )
        return self.get_resident(resident_id)  # type: ignore[return-value]

    def get_resident(self, resident_id: str) -> Resident | None:
        row = self.fetchone("SELECT * FROM residents WHERE id = ?", (resident_id,))
        if row is None:
            return None
        return Resident(
            id=row["id"],
            first_name=row["first_name"],
            email=row["email"],
            preferred_language=row["preferred_language"],
            city=row["city"],
            neighborhood=row["neighborhood"],
            location_radius_km=row["location_radius_km"],
            social_comfort=row["social_comfort"],
            preferred_group_size_min=row["preferred_group_size_min"],
            preferred_group_size_max=row["preferred_group_size_max"],
            cost_sensitivity=row["cost_sensitivity"],
            status=row["status"],
            created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
            withdrawn_at=parse_dt(row["withdrawn_at"]),
        )

    def list_residents(self, *, status: ResidentStatus | None = None) -> list[Resident]:
        if status is None:
            rows = self.fetchall("SELECT * FROM residents ORDER BY created_at DESC")
        else:
            rows = self.fetchall(
                "SELECT * FROM residents WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        return [
            Resident(
                id=row["id"],
                first_name=row["first_name"],
                email=row["email"],
                preferred_language=row["preferred_language"],
                city=row["city"],
                neighborhood=row["neighborhood"],
                location_radius_km=row["location_radius_km"],
                social_comfort=row["social_comfort"],
                preferred_group_size_min=row["preferred_group_size_min"],
                preferred_group_size_max=row["preferred_group_size_max"],
                cost_sensitivity=row["cost_sensitivity"],
                status=row["status"],
                created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
                updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
                withdrawn_at=parse_dt(row["withdrawn_at"]),
            )
            for row in rows
        ]

    def add_preference(
        self,
        *,
        resident_id: str,
        preference_type: str,
        value: str,
    ) -> ResidentPreference:
        preference_id = new_id("pref")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_preferences (id, resident_id, preference_type, value, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (preference_id, resident_id, preference_type, value, now),
        )
        return ResidentPreference(
            id=preference_id,
            resident_id=resident_id,
            preference_type=preference_type,  # type: ignore[arg-type]
            value=value,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def add_availability(
        self,
        *,
        resident_id: str,
        weekday: str,
        start_time_local: str,
        end_time_local: str,
    ) -> ResidentAvailability:
        availability_id = new_id("avail")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_availability (id, resident_id, weekday, start_time_local, end_time_local, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (availability_id, resident_id, weekday, start_time_local, end_time_local, now),
        )
        return ResidentAvailability(
            id=availability_id,
            resident_id=resident_id,
            weekday=weekday,  # type: ignore[arg-type]
            start_time_local=start_time_local,
            end_time_local=end_time_local,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def add_avoidance(self, *, resident_id: str, value: str) -> ResidentAvoidance:
        avoidance_id = new_id("avoid")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_avoidances (id, resident_id, value, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (avoidance_id, resident_id, value, now),
        )
        return ResidentAvoidance(
            id=avoidance_id,
            resident_id=resident_id,
            value=value,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def update_resident_status(self, *, resident_id: str, status: ResidentStatus) -> None:
        self.execute(
            "UPDATE residents SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now_iso(), resident_id),
        )

