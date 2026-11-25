class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    code = "validation_error"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class VerificationRequiredError(DomainError):
    status_code = 403
    code = "phone_verification_required"
