"""AirportIQ custom exceptions and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import re

from app.models.airport import normalize_iata


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class AirportIQError(Exception):
    """Base exception for all AirportIQ domain errors."""

    def __init__(self, detail: str = "An internal error occurred.") -> None:
        self.detail = detail
        super().__init__(detail)


class UnknownAirportError(AirportIQError):
    """Raised when a requested airport code is not in the supported set."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"{code} is not a supported or recognized airport code.")


class ProviderError(AirportIQError):
    """Raised when an upstream data provider fails unrecoverably."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        super().__init__(f"Provider {provider} failed: {reason}")


# ---------------------------------------------------------------------------
# Friendly Pydantic validation formatter
# ---------------------------------------------------------------------------


def _format_validation_errors(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for err in exc.errors():
        loc = " → ".join(str(part) for part in err["loc"])
        raw_input = err.get("input")

        if raw_input is not None:
            try:
                normalize_iata(str(raw_input))
            except ValueError:
                messages.append(
                    f"{raw_input} is not a valid IATA airport code (use 3 letters)."
                )
                continue
        messages.append(f"{loc}: {err['msg']}")
    return messages


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach custom exception handlers to *app*."""

    @app.exception_handler(UnknownAirportError)
    async def _unknown_airport(
        _request: Request, exc: UnknownAirportError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    @app.exception_handler(ProviderError)
    async def _provider_error(
        _request: Request, exc: ProviderError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": exc.detail})

    @app.exception_handler(AirportIQError)
    async def _base_error(
        _request: Request, exc: AirportIQError
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": exc.detail})

    @app.exception_handler(ValidationError)
    async def _validation_error(
        _request: Request, exc: ValidationError
    ) -> JSONResponse:
        messages = _format_validation_errors(exc)
        detail = messages[0] if len(messages) == 1 else messages
        return JSONResponse(status_code=422, content={"detail": detail})
