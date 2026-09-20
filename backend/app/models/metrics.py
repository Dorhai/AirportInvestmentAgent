from __future__ import annotations

import logging
from typing import Annotated, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, computed_field
from pydantic import Discriminator, Tag

from app.models.airport import IATA, Airport

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Origin variants
# ---------------------------------------------------------------------------


class Live(BaseModel, frozen=True):
    kind: Literal["live"] = "live"
    source: str
    period: str
    fetched_at: str


class Sample(BaseModel, frozen=True):
    kind: Literal["sample"] = "sample"
    source: str
    period: str
    citation: str


class Derived(BaseModel, frozen=True):
    kind: Literal["derived"] = "derived"
    method: str
    inputs: tuple[str, ...]
    period: str
    sources: tuple[str, ...]
    freshness: Literal["live", "sample", "mixed"]


class Proxy(BaseModel, frozen=True):
    kind: Literal["proxy"] = "proxy"
    method: str
    inputs: tuple[str, ...]
    assumption: str
    period: str
    sources: tuple[str, ...]
    freshness: Literal["live", "sample", "mixed"]


class Scenario(BaseModel, frozen=True):
    kind: Literal["scenario"] = "scenario"
    adjustment: str
    baseline_origin: Origin
    period: str


def _origin_discriminator(v: dict | BaseModel) -> str:
    if isinstance(v, dict):
        return v.get("kind", "live")
    return getattr(v, "kind", "live")


Origin = Annotated[
    Union[
        Annotated[Live, Tag("live")],
        Annotated[Sample, Tag("sample")],
        Annotated[Derived, Tag("derived")],
        Annotated[Proxy, Tag("proxy")],
        Annotated[Scenario, Tag("scenario")],
    ],
    Discriminator(_origin_discriminator),
]

Scenario.model_rebuild()

# ---------------------------------------------------------------------------
# fold_origins
# ---------------------------------------------------------------------------


def fold_origins(
    *origins: Origin,
    method: str,
    proxy: bool = False,
    assumption: str | None = None,
) -> Derived | Proxy:
    all_sources: list[str] = []
    all_inputs: list[str] = []
    periods: list[str] = []
    has_live = False
    has_sample = False
    is_proxy = proxy

    for o in origins:
        all_inputs.append(o.kind)

        if isinstance(o, (Live,)):
            all_sources.append(o.source)
            has_live = True
        elif isinstance(o, (Sample,)):
            all_sources.append(o.source)
            has_sample = True
        elif isinstance(o, (Derived, Proxy)):
            all_sources.extend(o.sources)
            if o.freshness == "live":
                has_live = True
            elif o.freshness == "sample":
                has_sample = True
            else:
                has_live = True
                has_sample = True
            if isinstance(o, Proxy):
                is_proxy = True
        elif isinstance(o, Scenario):
            all_inputs.append(f"scenario:{o.adjustment}")

        if hasattr(o, "period"):
            periods.append(o.period)

    unique_sources = tuple(dict.fromkeys(all_sources))
    unique_periods = list(dict.fromkeys(periods))

    if len(unique_periods) > 1:
        logger.warning("Mismatched periods in fold_origins: %s", unique_periods)

    combined_period = "; ".join(unique_periods) if unique_periods else ""

    if has_live and has_sample:
        freshness: Literal["live", "sample", "mixed"] = "mixed"
    elif has_sample:
        freshness = "sample"
    else:
        freshness = "live"

    if is_proxy:
        return Proxy(
            method=method,
            inputs=tuple(all_inputs),
            assumption=assumption or "",
            period=combined_period,
            sources=unique_sources,
            freshness=freshness,
        )
    return Derived(
        method=method,
        inputs=tuple(all_inputs),
        period=combined_period,
        sources=unique_sources,
        freshness=freshness,
    )


# ---------------------------------------------------------------------------
# Datum wrapper
# ---------------------------------------------------------------------------


class Absent(BaseModel, frozen=True):
    kind: Literal["absent"] = "absent"
    reason: Literal[
        "NOT_PUBLISHED", "PROVIDER_FAILED", "NO_DEPARTURES", "OUT_OF_SCOPE"
    ]
    detail: str
    attempted: tuple[str, ...]


class Present(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    kind: Literal["present"] = "present"
    value: T
    origin: Origin


def _datum_discriminator(v: dict | BaseModel) -> str:
    if isinstance(v, dict):
        return v.get("kind", "present")
    return getattr(v, "kind", "present")


DatumInt = Annotated[
    Union[
        Annotated[Present[int], Tag("present")],
        Annotated[Absent, Tag("absent")],
    ],
    Discriminator(_datum_discriminator),
]

DatumFloat = Annotated[
    Union[
        Annotated[Present[float], Tag("present")],
        Annotated[Absent, Tag("absent")],
    ],
    Discriminator(_datum_discriminator),
]

# ---------------------------------------------------------------------------
# AirportMetrics
# ---------------------------------------------------------------------------

_CORE_SCORING_KPI_FIELDS: tuple[str, ...] = (
    "passenger_volume",
    "previous_passenger_volume",
    "annual_operations",
    "delayed_flights_pct",
    "average_delay_minutes",
)

_METRIC_FIELDS: tuple[str, ...] = _CORE_SCORING_KPI_FIELDS + (
    "long_haul_flights",
    "total_departures",
    "international_departures",
    "average_flight_distance_sm",
)


class AirportMetrics(BaseModel, frozen=True):
    airport_code: IATA
    airport_name: str = ""
    passenger_volume: DatumInt
    previous_passenger_volume: DatumInt
    annual_operations: DatumInt
    delayed_flights_pct: DatumFloat
    average_delay_minutes: DatumFloat
    long_haul_flights: DatumInt
    total_departures: DatumInt
    international_departures: DatumInt = Absent(reason="NOT_PUBLISHED", detail="default", attempted=())
    average_flight_distance_sm: DatumFloat = Absent(reason="NOT_PUBLISHED", detail="default", attempted=())
    warnings: list[str] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sources(self) -> list[str]:
        seen: dict[str, None] = {}
        for name in _METRIC_FIELDS:
            datum = getattr(self, name)
            if isinstance(datum, Present):
                origin = datum.origin
                if isinstance(origin, (Live, Sample)):
                    seen.setdefault(origin.source, None)
                elif isinstance(origin, (Derived, Proxy)):
                    for s in origin.sources:
                        seen.setdefault(s, None)
        return list(seen)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def data_period(self) -> str:
        periods: list[str] = []
        for name in _METRIC_FIELDS:
            datum = getattr(self, name)
            if isinstance(datum, Present) and hasattr(datum.origin, "period"):
                periods.append(datum.origin.period)
        unique = list(dict.fromkeys(periods))
        return "; ".join(unique)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def core_completeness_score(self) -> float:
        present_count = sum(
            1
            for name in _CORE_SCORING_KPI_FIELDS
            if isinstance(getattr(self, name), Present)
        )
        return present_count / len(_CORE_SCORING_KPI_FIELDS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completeness_score(self) -> float:
        present_count = sum(
            1
            for name in _METRIC_FIELDS
            if isinstance(getattr(self, name), Present)
        )
        return present_count / len(_METRIC_FIELDS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def freshness(self) -> Literal["live", "sample", "mixed"]:
        has_live = False
        has_sample = False
        for name in _METRIC_FIELDS:
            datum = getattr(self, name)
            if not isinstance(datum, Present):
                continue
            origin = datum.origin
            if isinstance(origin, Live):
                has_live = True
            elif isinstance(origin, Sample):
                has_sample = True
            elif isinstance(origin, (Derived, Proxy)):
                if origin.freshness == "live":
                    has_live = True
                elif origin.freshness == "sample":
                    has_sample = True
                else:
                    has_live = True
                    has_sample = True
        if has_live and has_sample:
            return "mixed"
        if has_sample:
            return "sample"
        return "live"


# ---------------------------------------------------------------------------
# AirportDossier
# ---------------------------------------------------------------------------


from app.models.context import AirportContext
from app.analytics.long_haul import LongHaulSummary

class AirportDossier(BaseModel, frozen=True):
    airport: Airport
    metrics: AirportMetrics
    passenger_growth: DatumFloat
    long_haul_pct: DatumFloat
    long_haul_summary: LongHaulSummary | None = None
    unmet_demand_index: DatumFloat
    context: AirportContext
    snapshot_at: str
