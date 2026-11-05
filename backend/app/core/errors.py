"""Domain errors. Services raise them; one handler turns them into HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base error. Each subclass names its HTTP status, like Spring's @ResponseStatus."""

    status_code = 400
    detail = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)

    @property
    def headers(self) -> dict[str, str] | None:
        return None


class Unauthorized(DomainError):
    status_code = 401
    detail = "Sign in required"


class Forbidden(DomainError):
    status_code = 403
    detail = "Forbidden"


class NotFound(DomainError):
    status_code = 404
    detail = "Not found"


class Conflict(DomainError):
    status_code = 409
    detail = "Conflict"


class TooManyRequests(DomainError):
    status_code = 429
    detail = "Too many attempts. Try again later."

    def __init__(self, retry_after: int, detail: str | None = None) -> None:
        super().__init__(detail)
        self.retry_after = retry_after

    @property
    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after)}


def register_error_handlers(app: FastAPI) -> None:
    # Same body shape as FastAPI's own errors: {"detail": ...}.
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )
