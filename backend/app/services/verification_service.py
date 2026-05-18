"""
Stub verification for Dutch professional registers.

In production this hits three external APIs:
- Vektis AGB-register   (personal AGB + onderneming AGB)
- CIBG BIG-register     (Wet BIG article 3 roles only)
- KvK                   (the onderneming exists, lists vestigingen)

For the prototype, all three are stubbed. The stub accepts any plausibly
shaped AGB code (8 digits, leading "01" or "91"), returns canned register
payloads in the same shape the real APIs would, and surfaces the same
fields the production flow would persist in `professional_verifications`.

Required roles per the NL briefing (§2.2):
- huisarts / psycholoog / psychotherapeut  -> BIG check required
- poh-ggz / doktersassistent / welzijnscoach -> BIG optional
"""

from __future__ import annotations

import json
from dataclasses import dataclass

BIG_REQUIRED_QUALIFICATIONS = frozenset({"huisarts", "psycholoog", "psychotherapeut"})

# Maps an 8-digit AGB prefix to the qualification the register would return.
# The real register uses the full code, but a prefix is enough for a demo stub.
_AGB_PREFIX_TO_QUALIFICATION: dict[str, str] = {
    "0101": "huisarts",
    "0102": "huisarts",
    "9491": "poh-ggz",
    "9492": "poh-ggz",
    "9405": "doktersassistent",
    "9442": "psycholoog",
    "9443": "psychotherapeut",
}


class VerificationFailure(Exception):
    """Raised when the stub verifier cannot approve a professional."""


@dataclass(slots=True)
class VerificationResult:
    qualification: str
    onderneming_agb_code: str
    agb_response_json: str
    big_response_json: str | None
    kvk_response_json: str
    big_required: bool


def _is_plausible_agb(code: str) -> bool:
    if not code or not code.isdigit() or len(code) != 8:
        return False
    return code.startswith(("01", "91", "94"))


def _is_plausible_big(big_number: str) -> bool:
    return bool(big_number) and big_number.isdigit() and 8 <= len(big_number) <= 11


def _qualification_for(agb_code: str, hint: str | None) -> str:
    prefix = agb_code[:4]
    return _AGB_PREFIX_TO_QUALIFICATION.get(prefix, hint or "huisarts")


class StubVerificationService:
    """
    Always-pass stub. Accepts any plausibly shaped AGB; rejects obviously
    malformed input so we can demo both the success and failure paths.

    Replace this class with a real Vektis/CIBG/KvK client in production
    without changing any caller.
    """

    def verify(
        self,
        *,
        agb_code: str,
        big_number: str | None = None,
        kvk_number: str | None = None,
        qualification_hint: str | None = None,
    ) -> VerificationResult:
        if not _is_plausible_agb(agb_code):
            raise VerificationFailure(
                f"AGB code {agb_code!r} is not a plausible 8-digit AGB"
            )

        qualification = _qualification_for(agb_code, qualification_hint)
        big_required = qualification in BIG_REQUIRED_QUALIFICATIONS

        if big_required:
            if big_number is None:
                raise VerificationFailure(
                    f"Qualification {qualification!r} requires a BIG number"
                )
            if not _is_plausible_big(big_number):
                raise VerificationFailure(
                    f"BIG number {big_number!r} is not plausibly shaped"
                )

        onderneming_agb_code = f"01{agb_code[2:]}"  # synthesised practice AGB

        agb_response = {
            "active": True,
            "agb": agb_code,
            "qualification": qualification,
            "ondernemingAGB": onderneming_agb_code,
        }
        big_response: dict[str, object] | None
        if big_required and big_number is not None:
            big_response = {
                "bigNummer": big_number,
                "status": "active",
                "beroep": "arts" if qualification == "huisarts" else qualification,
                "discipline": "huisartsgeneeskunde" if qualification == "huisarts" else qualification,
            }
        else:
            big_response = None

        kvk_response = {
            "kvkNummer": kvk_number or f"KVK-{onderneming_agb_code}",
            "naam": "Huisartsenpraktijk (stub)",
            "vestigingen": [{"vestigingsnummer": "000000000001"}],
        }

        return VerificationResult(
            qualification=qualification,
            onderneming_agb_code=onderneming_agb_code,
            agb_response_json=json.dumps(agb_response, sort_keys=True),
            big_response_json=(
                json.dumps(big_response, sort_keys=True) if big_response else None
            ),
            kvk_response_json=json.dumps(kvk_response, sort_keys=True),
            big_required=big_required,
        )
