import re
from dataclasses import dataclass

from app.domain.errors import ValidationError, VerificationRequiredError

AFFIRMATIVE_RESPONSES = {"yes", "y", "yeah", "yep", "correct", "confirm", "confirmed", "i confirm"}


def normalize_phone_number(spoken_phone: str, default_country_code: str = "+91") -> str:
    """Normalize an Indian local number or an E.164 number for durable matching."""
    cleaned = re.sub(r"[\s().-]", "", spoken_phone.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+"):
        digits = cleaned[1:]
    else:
        digits = cleaned
        if len(digits) == 10:
            digits = default_country_code.lstrip("+") + digits
    if not digits.isdigit() or not 10 <= len(digits) <= 15:
        raise ValidationError("Please provide a valid phone number with 10 to 15 digits.")
    return f"+{digits}"


def phone_readback(phone_number: str) -> str:
    return " ".join(phone_number.removeprefix("+"))


@dataclass
class CallSessionPhoneVerification:
    """State owned by a call session; it is intentionally independent of Pipecat."""

    phone_number: str | None = None
    is_verified: bool = False

    def capture_spoken_phone(self, spoken_phone: str) -> str:
        normalized = normalize_phone_number(spoken_phone)
        if normalized != self.phone_number:
            self.phone_number = normalized
            self.is_verified = False
        return normalized

    def digit_by_digit_readback(self) -> str:
        if self.phone_number is None:
            raise ValidationError("A phone number must be captured before it can be read back.")
        return phone_readback(self.phone_number)

    def confirm_phone(self, caller_response: str) -> bool:
        if self.phone_number is None:
            raise ValidationError("A phone number must be captured before it can be confirmed.")
        self.is_verified = caller_response.strip().lower() in AFFIRMATIVE_RESPONSES
        return self.is_verified

    def require_verified_phone(self) -> str:
        if self.phone_number is None or not self.is_verified:
            raise VerificationRequiredError("Explicit phone-number confirmation is required before this action.")
        return self.phone_number
