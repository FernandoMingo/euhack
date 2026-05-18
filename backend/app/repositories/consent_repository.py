from __future__ import annotations

from collections.abc import Iterable

from app.dataclasses import (
    CaptureMethod,
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
)
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


class ConsentRepository(RepositoryBase):
    def create_consent(
        self,
        *,
        resident_id: str,
        professional_id: str,
        scopes: Iterable[str],
        consent_text_version: str = "v1.0-nl-2026-05",
        consent_locale: str = "nl",
        capture_method: CaptureMethod = "in_consult",
    ) -> ConsentRecord:
        consent_id = new_id("consent")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO consent_records (
                id, resident_id, professional_id, status, granted_at, created_at,
                consent_text_version, consent_locale, capture_method
            ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            (
                consent_id,
                resident_id,
                professional_id,
                now,
                now,
                consent_text_version,
                consent_locale,
                capture_method,
            ),
        )
        scope_list = list(dict.fromkeys(scopes))
        if not scope_list:
            raise ValueError("Consent must include at least one scope")
        for scope in scope_list:
            self.execute(
                "INSERT INTO consent_scopes (id, consent_id, scope) VALUES (?, ?, ?)",
                (new_id("scope"), consent_id, scope),
            )
        return ConsentRecord(
            id=consent_id,
            resident_id=resident_id,
            professional_id=professional_id,
            status="active",
            granted_at=parse_dt(now),  # type: ignore[arg-type]
            created_at=parse_dt(now),  # type: ignore[arg-type]
            consent_text_version=consent_text_version,
            consent_locale=consent_locale,
            capture_method=capture_method,
        )

    def get_consent(self, consent_id: str) -> ConsentRecord | None:
        row = self.fetchone(
            "SELECT * FROM consent_records WHERE id = ?",
            (consent_id,),
        )
        if row is None:
            return None
        return ConsentRecord(
            id=row["id"],
            resident_id=row["resident_id"],
            professional_id=row["professional_id"],
            status=row["status"],
            granted_at=parse_dt(row["granted_at"]),  # type: ignore[arg-type]
            created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            consent_text_version=row["consent_text_version"],
            consent_locale=row["consent_locale"],
            capture_method=row["capture_method"],
            revoked_at=parse_dt(row["revoked_at"]),
        )

    def list_scopes(self, consent_id: str) -> list[ConsentScope]:
        rows = self.fetchall(
            "SELECT * FROM consent_scopes WHERE consent_id = ? ORDER BY scope",
            (consent_id,),
        )
        return [
            ConsentScope(id=row["id"], consent_id=row["consent_id"], scope=row["scope"])
            for row in rows
        ]

    def list_active_for_resident(self, resident_id: str) -> list[ConsentRecord]:
        rows = self.fetchall(
            "SELECT * FROM consent_records WHERE resident_id = ? AND status = 'active' "
            "ORDER BY granted_at DESC",
            (resident_id,),
        )
        return [
            ConsentRecord(
                id=row["id"],
                resident_id=row["resident_id"],
                professional_id=row["professional_id"],
                status=row["status"],
                granted_at=parse_dt(row["granted_at"]),  # type: ignore[arg-type]
                created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
                consent_text_version=row["consent_text_version"],
                consent_locale=row["consent_locale"],
                capture_method=row["capture_method"],
                revoked_at=parse_dt(row["revoked_at"]),
            )
            for row in rows
        ]

    def revoke_consent(self, consent_id: str) -> None:
        now = utc_now_iso()
        self.execute(
            "UPDATE consent_records SET status = 'revoked', revoked_at = ? WHERE id = ? "
            "AND status = 'active'",
            (now, consent_id),
        )

    def update_status(self, *, consent_id: str, status: ConsentStatus) -> None:
        if status == "revoked":
            self.revoke_consent(consent_id)
        else:
            self.execute(
                "UPDATE consent_records SET status = ?, revoked_at = NULL WHERE id = ?",
                (status, consent_id),
            )
