from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from app.models.airport import IATA
from app.models.context import AirportContext
from app.models.metrics import (
    Absent,
    AirportMetrics,
    Present,
    _METRIC_FIELDS,
)
from app.models.score import ProviderFailure

logger = logging.getLogger(__name__)

MetricField = Literal[
    "passenger_volume",
    "previous_passenger_volume",
    "annual_operations",
    "delayed_flights_pct",
    "average_delay_minutes",
    "long_haul_flights",
    "total_departures",
    "international_departures",
    "average_flight_distance_sm",
]


class ProviderOutcome(BaseModel, frozen=True):
    fields: dict[str, dict[str, Present]]  # airport_code -> field_name -> Present
    failures: list[ProviderFailure]
    warnings: dict[str, list[str]] = {}  # airport_code -> warnings


class ContextOutcome(BaseModel, frozen=True):
    fields: dict[str, dict[str, Any]]  # airport_code -> field_name -> Any
    failures: list[ProviderFailure]
    warnings: dict[str, list[str]] = {}


@runtime_checkable
class AviationProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome: ...


@runtime_checkable
class ContextProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome: ...


def merge_outcomes(
    codes: Sequence[IATA],
    outcomes: Sequence[ProviderOutcome],
) -> dict[str, AirportMetrics]:
    all_failures: list[ProviderFailure] = []
    for o in outcomes:
        all_failures.extend(o.failures)

    failure_providers = tuple(dict.fromkeys(f.provider for f in all_failures))
    failure_reasons = "; ".join(
        dict.fromkeys(f"{f.provider}: {f.error}" for f in all_failures)
    )

    result: dict[str, AirportMetrics] = {}

    for code in codes:
        merged: dict[str, Present | Absent] = {}
        airport_warnings: list[str] = []

        for field_name in _METRIC_FIELDS:
            datum: Present | Absent | None = None
            for outcome in outcomes:
                airport_fields = outcome.fields.get(code, {})
                if field_name in airport_fields:
                    datum = airport_fields[field_name]
                    break

            if datum is None:
                reason: Literal[
                    "NOT_PUBLISHED", "PROVIDER_FAILED", "NO_DEPARTURES", "OUT_OF_SCOPE"
                ] = "PROVIDER_FAILED" if failure_providers else "NOT_PUBLISHED"
                datum = Absent(
                    reason=reason,
                    detail=failure_reasons or f"{field_name} not available from any provider",
                    attempted=failure_providers,
                )

            merged[field_name] = datum

        for outcome in outcomes:
            airport_warnings.extend(outcome.warnings.get(code, []))

        result[code] = AirportMetrics(airport_code=code, warnings=airport_warnings, **merged)  # type: ignore[arg-type]

    return result


def merge_context_outcomes(
    codes: Sequence[IATA],
    outcomes: Sequence[ContextOutcome],
) -> dict[str, AirportContext]:
    result: dict[str, AirportContext] = {}

    for code in codes:
        merged: dict[str, Any] = {}
        for outcome in outcomes:
            airport_fields = outcome.fields.get(code, {})
            for k, v in airport_fields.items():
                if k not in merged:
                    merged[k] = v
        result[code] = AirportContext(**merged)

    return result
