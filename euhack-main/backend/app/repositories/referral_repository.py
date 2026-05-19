from __future__ import annotations

from app.dataclasses import Referral, ReferralStatus
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


class ReferralRepository(RepositoryBase):
    def create_referral(
        self,
        *,
        resident_id: str,
        professional_id: str,
        referral_reason: str | None = None,
        status: ReferralStatus = "submitted",
    ) -> Referral:
        referral_id = new_id("referral")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO referrals (
                id, resident_id, professional_id, referral_reason, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (referral_id, resident_id, professional_id, referral_reason, status, now),
        )
        return Referral(
            id=referral_id,
            resident_id=resident_id,
            professional_id=professional_id,
            referral_reason=referral_reason,
            status=status,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def get_referral(self, referral_id: str) -> Referral | None:
        row = self.fetchone("SELECT * FROM referrals WHERE id = ?", (referral_id,))
        if row is None:
            return None
        return Referral(
            id=row["id"],
            resident_id=row["resident_id"],
            professional_id=row["professional_id"],
            referral_reason=row["referral_reason"],
            status=row["status"],
            created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            closed_at=parse_dt(row["closed_at"]),
        )

    def list_for_professional(self, professional_id: str) -> list[Referral]:
        rows = self.fetchall(
            "SELECT * FROM referrals WHERE professional_id = ? ORDER BY created_at DESC",
            (professional_id,),
        )
        return [
            Referral(
                id=row["id"],
                resident_id=row["resident_id"],
                professional_id=row["professional_id"],
                referral_reason=row["referral_reason"],
                status=row["status"],
                created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
                closed_at=parse_dt(row["closed_at"]),
            )
            for row in rows
        ]

    def update_status(self, *, referral_id: str, status: ReferralStatus) -> None:
        if status == "closed":
            self.execute(
                "UPDATE referrals SET status = 'closed', closed_at = ? WHERE id = ?",
                (utc_now_iso(), referral_id),
            )
        else:
            self.execute(
                "UPDATE referrals SET status = ?, closed_at = NULL WHERE id = ?",
                (status, referral_id),
            )
