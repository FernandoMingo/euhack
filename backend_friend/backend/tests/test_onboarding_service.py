from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import connect, init_db  # noqa: E402
from app.repositories import (  # noqa: E402
    ConsentRepository,
    ProfessionalRepository,
    ReferralRepository,
    ResidentRepository,
)
from app.services.onboarding_service import (  # noqa: E402
    OnboardingService,
    ResidentProfileInput,
)


class OnboardingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        # ignore_cleanup_errors works around Windows holding the SQLite WAL/SHM
        # files briefly after connection close. The actual files leak into the
        # OS temp dir, but the test itself completes cleanly.
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "test.db"
        init_db(db_path=self.db_path)

    def _new_service(self) -> tuple[OnboardingService, "connect"]:  # type: ignore[name-defined]
        conn = connect(db_path=self.db_path)
        return OnboardingService(conn), conn

    def test_signup_professional_happy_path(self) -> None:
        service, conn = self._new_service()
        try:
            result = service.signup_professional(
                full_name="Dr. Anna Vermeer",
                role="huisarts",
                email="anna@example.com",
                agb_code="01024587",
                big_number="12345678",
            )

            self.assertEqual(result.professional.verification_status, "approved")
            self.assertEqual(result.verification.outcome, "passed")
            self.assertEqual(result.professional.qualification, "huisarts")
            self.assertIsNotNone(result.professional.onderneming_agb_code)
            self.assertIsNotNone(result.professional.verified_at)

            repo = ProfessionalRepository(conn)
            history = repo.list_verifications(professional_id=result.professional.id)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].outcome, "passed")
        finally:
            conn.close()

    def test_signup_professional_rejects_malformed_agb(self) -> None:
        service, conn = self._new_service()
        try:
            result = service.signup_professional(
                full_name="Bad Form",
                role="huisarts",
                email="bad@example.com",
                agb_code="ABC",
                big_number="12345678",
            )
            self.assertEqual(result.professional.verification_status, "rejected")
            self.assertEqual(result.verification.outcome, "failed")
            self.assertIn("plausible", (result.verification.failure_reason or "").lower())
        finally:
            conn.close()

    def test_signup_professional_requires_big_for_huisarts(self) -> None:
        service, conn = self._new_service()
        try:
            result = service.signup_professional(
                full_name="No BIG",
                role="huisarts",
                email="nobig@example.com",
                agb_code="01099999",
                big_number=None,
            )
            self.assertEqual(result.professional.verification_status, "rejected")
            self.assertEqual(result.verification.outcome, "failed")
        finally:
            conn.close()

    def test_signup_professional_poh_ggz_does_not_need_big(self) -> None:
        service, conn = self._new_service()
        try:
            result = service.signup_professional(
                full_name="Sanne POH-GGZ",
                role="poh-ggz",
                email="sanne@example.com",
                agb_code="94918888",
                big_number=None,
                qualification_hint="poh-ggz",
            )
            self.assertEqual(result.professional.verification_status, "approved")
            self.assertEqual(result.professional.qualification, "poh-ggz")
        finally:
            conn.close()

    def test_signup_rejects_duplicate_email(self) -> None:
        service, conn = self._new_service()
        try:
            service.signup_professional(
                full_name="A",
                role="huisarts",
                email="dup@example.com",
                agb_code="01010001",
                big_number="12345678",
            )
            with self.assertRaises(ValueError):
                service.signup_professional(
                    full_name="B",
                    role="huisarts",
                    email="dup@example.com",
                    agb_code="01010002",
                    big_number="12345678",
                )
        finally:
            conn.close()

    def test_create_referral_creates_consent_and_resident(self) -> None:
        service, conn = self._new_service()
        try:
            signup = service.signup_professional(
                full_name="Dr. Anna",
                role="huisarts",
                email="anna2@example.com",
                agb_code="01024501",
                big_number="11111111",
            )

            profile = ResidentProfileInput(
                first_name="Sofia",
                email="sofia@example.com",
                preferred_language="nl",
                city="Amsterdam",
                social_comfort="small_group_low_pressure",
                preferred_group_size_min=3,
                preferred_group_size_max=6,
                cost_sensitivity="free_or_low_cost",
                neighborhood="Oud-West",
                interests=("photography", "parks"),
                availability=(("sat", "10:00", "12:00"),),
                avoidances=("alcohol",),
            )
            result = service.create_referral(
                professional_id=signup.professional.id,
                profile=profile,
                referral_reason="loneliness, recently moved",
            )

            self.assertEqual(result.resident.first_name, "Sofia")
            self.assertEqual(result.consent.status, "active")
            self.assertEqual(result.consent.capture_method, "in_consult")
            self.assertEqual(result.referral.status, "submitted")
            self.assertEqual(result.referral.professional_id, signup.professional.id)

            consents = ConsentRepository(conn)
            scopes = consents.list_scopes(result.consent.id)
            self.assertEqual(
                sorted(s.scope for s in scopes),
                sorted(
                    [
                        "create_social_profile",
                        "use_profile_for_activity_matching",
                        "send_activity_invitations",
                        "share_limited_status_with_professional",
                    ]
                ),
            )

            residents = ResidentRepository(conn)
            stored = residents.get_resident(result.resident.id)
            self.assertIsNotNone(stored)

            referrals = ReferralRepository(conn)
            for_prof = referrals.list_for_professional(signup.professional.id)
            self.assertEqual(len(for_prof), 1)
        finally:
            conn.close()

    def test_referral_blocked_for_unapproved_professional(self) -> None:
        service, conn = self._new_service()
        try:
            signup = service.signup_professional(
                full_name="Rejected Doc",
                role="huisarts",
                email="rejected@example.com",
                agb_code="0001ABCD",
                big_number="12345678",
            )
            self.assertEqual(signup.professional.verification_status, "rejected")

            profile = ResidentProfileInput(
                first_name="X",
                email="x@example.com",
                preferred_language="nl",
                city="Amsterdam",
                social_comfort="small_group_low_pressure",
                preferred_group_size_min=3,
                preferred_group_size_max=6,
                cost_sensitivity="free_or_low_cost",
            )
            with self.assertRaises(ValueError):
                service.create_referral(
                    professional_id=signup.professional.id,
                    profile=profile,
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
