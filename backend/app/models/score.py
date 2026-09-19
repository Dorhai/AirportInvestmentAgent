from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, computed_field

from app.models.airport import IATA
from app.models.context import AirportContext
from app.models.metrics import (
    Absent,
    DatumFloat,
    Derived,
    Live,
    Present,
    Proxy,
    Sample,
)

Confidence = Literal["HIGH", "MEDIUM", "LOW"]

_SCORE_FIELDS: tuple[str, ...] = (
    "opportunity_score",
    "demand_growth_score",
    "congestion_score",
    "delay_pressure_score",
    "capacity_pressure_score",
)


class ProviderFailure(BaseModel, frozen=True):
    provider: str
    error: str


class PeerStats(BaseModel, frozen=True):
    bounds: dict[str, tuple[float, float]]
    universe_codes: tuple[str, ...]


class ScoringMethodology(BaseModel, frozen=True):
    weights: dict[str, float]
    component_labels: dict[str, str]
    rules: list[str]


class AirportScore(BaseModel, frozen=True):
    airport_code: IATA
    airport_name: str = ""
    opportunity_score: DatumFloat
    demand_growth_score: DatumFloat
    congestion_score: DatumFloat
    delay_pressure_score: DatumFloat
    capacity_pressure_score: DatumFloat
    confidence: Confidence
    context: AirportContext | None = None
    snapshot_at: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def assumptions(self) -> list[str]:
        out: list[str] = []
        for name in _SCORE_FIELDS:
            datum = getattr(self, name)
            if isinstance(datum, Present) and isinstance(datum.origin, Proxy):
                out.append(datum.origin.assumption)
        return out

    @computed_field  # type: ignore[prop-decorator]
    @property
    def limitations(self) -> list[str]:
        out: list[str] = []
        for name in _SCORE_FIELDS:
            datum = getattr(self, name)
            if isinstance(datum, Absent):
                out.append(datum.reason)
        return out

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sources(self) -> list[str]:
        seen: dict[str, None] = {}
        for name in _SCORE_FIELDS:
            datum = getattr(self, name)
            if not isinstance(datum, Present):
                continue
            origin = datum.origin
            if isinstance(origin, (Live, Sample)):
                seen.setdefault(origin.source, None)
            elif isinstance(origin, (Derived, Proxy)):
                for s in origin.sources:
                    seen.setdefault(s, None)
        return list(seen)
