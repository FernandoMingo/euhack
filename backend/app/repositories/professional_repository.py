from __future__ import annotations

from sqlite3 import Row

from app.dataclasses import (
    ProfessionalVerification,
    TrustedProfessional,
    VerificationOutcome,
    VerificationStatus,
)
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


def _row_to_professional(row: Row) -> TrustedProfessional:
    return TrustedProfessional(
        id=row["id"],
        full_name=row["full_name"],
        role=row["role"],
        organization=row["organization"],
        city=row["city"],
        email=row["email"],
        verification_status=row["verification_status"],
        created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
        updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        agb_code=row["agb_code"],
        big_number=row["big_number"],
        qualification=row["qualification"],
        onderneming_agb_code=row["onderneming_agb_code"],
        verified_at=parse_dt(row["verified_at"]),
    )


class ProfessionalRepository(RepositoryBase):
    def create_professional(
        self,
        *,
        full_name: str,
        role: str,
        email: str,
        organization: str | None = None,
        city: str | None = None,
        agb_code: str | None = None,
        big_number: str | None = None,
        qualification: str | None = None,
        onderneming_agb_code: str | None = None,
        verification_status: VerificationStatus = "pending",
    ) -> TrustedProfessional:
        professional_id = new_id("prof")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO trusted_professionals (
                id, full_name, role, organization, city, email, verification_status,
                agb_code, big_number, qualification, onderneming_agb_code,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                professional_id,
                full_name,
                role,
                organization,
                city,
                email,
                verification_status,
                agb_code,
                big_number,
                qualification,
                onderneming_agb_code,
                now,
                now,
            ),
        )
        return self.get_professional(professional_id)  # type: ignore[return-value]

    def get_professional(self, professional_id: str) -> TrustedProfessional | None:
        row = self.fetchone(
            "SELECT * FROM trusted_professionals WHERE id = ?",
            (professional_id,),
        )
        if row is None:
            return None
        return _row_to_professional(row)

    def get_professional_by_email(self, email: str) -> TrustedProfessional | None:
        row = self.fetchone(
            "SELECT * FROM trusted_professionals WHERE email = ?",
            (email,),
        )
        if row is None:
            return None
        return _row_to_professional(row)

    def get_professional_by_agb(self, agb_code: str) -> TrustedProfessional | None:
        row = self.fetchone(
            "SELECT * FROM trusted_professionals WHERE agb_code = ?",
            (agb_code,),
        )
        if row is None:
            return None
        return _row_to_professional(row)

    def list_professionals(
        self,
        *,
        verification_status: VerificationStatus | None = None,
    ) -> list[TrustedProfessional]:
        if verification_status is None:
            rows = self.fetchall(
                "SELECT * FROM trusted_professionals ORDER BY created_at DESC"
            )
        else:
            rows = self.fetchall(
                "SELECT * FROM trusted_professionals WHERE verification_status = ? "
                "ORDER BY created_at DESC",
                (verification_status,),
            )
        return [_row_to_professional(row) for row in rows]

    def mark_verified(
        self,
        *,
        professional_id: str,
        qualification: str | None = None,
        onderneming_agb_code: str | None = None,
    ) -> None:
        now = utc_now_iso()
        self.execute(
            """
            UPDATE trusted_professionals
            SET verification_status = 'approved',
                verified_at = ?,
                updated_at = ?,
                qualification = COALESCE(?, qualification),
                onderneming_agb_code = COALESCE(?, onderneming_agb_code)
            WHERE id = ?
            """,
            (now, now, qualification, onderneming_agb_code, professional_id),
        )

    def mark_rejected(self, *, professional_id: str) -> None:
        now = utc_now_iso()
        self.execute(
            """
            UPDATE trusted_professionals
            SET verification_status = 'rejected', updated_at = ?
            WHERE id = ?
            """,
            (now, professional_id),
        )

    def record_verification(
        self,
        *,
        professional_id: str,
        outcome: VerificationOutcome,
        agb_response_json: str | None = None,
        big_response_json: str | None = None,
        kvk_response_json: str | None = None,
        failure_reason: str | None = None,
    ) -> ProfessionalVerification:
        verification_id = new_id("verif")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO professional_verifications (
                id, professional_id, outcome, agb_response_json, big_response_json,
                kvk_response_json, failure_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verification_id,
                professional_id,
                outcome,
                agb_response_json,
                big_response_json,
                kvk_response_json,
                failure_reason,
                now,
            ),
        )
        return ProfessionalVerification(
            id=verification_id,
            professional_id=professional_id,
            outcome=outcome,
            agb_response_json=agb_response_json,
            big_response_json=big_response_json,
            kvk_response_json=kvk_response_json,
            failure_reason=failure_reason,
            created_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def list_verifications(self, *, professional_id: str) -> list[ProfessionalVerification]:
        rows = self.fetchall(
            "SELECT * FROM professional_verifications WHERE professional_id = ? "
            "ORDER BY created_at DESC",
            (professional_id,),
        )
        return [
            ProfessionalVerification(
                id=row["id"],
                professional_id=row["professional_id"],
                outcome=row["outcome"],
                agb_response_json=row["agb_response_json"],
                big_response_json=row["big_response_json"],
                kvk_response_json=row["kvk_response_json"],
                failure_reason=row["failure_reason"],
                created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            )
            for row in rows
        ]
