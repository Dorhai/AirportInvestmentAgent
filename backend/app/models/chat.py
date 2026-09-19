"""Agent result models and ChatResponse assembly."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Literal, Union, Any

from pydantic import BaseModel, Discriminator

from app.models.airport import IATA
from app.models.context import AirportContext
from app.models.metrics import (
    AirportMetrics,
    DatumFloat,
    Derived,
    Live,
    Present,
    Proxy,
    Sample,
)
from app.models.score import AirportScore, Confidence


# ---------------------------------------------------------------------------
# Result base
# ---------------------------------------------------------------------------


class ResultBase(BaseModel, frozen=True):
    airports: list[str]
    snapshot_at: str


# ---------------------------------------------------------------------------
# Tool result variants
# ---------------------------------------------------------------------------


class MetricsResult(ResultBase):
    kind: Literal["metrics"] = "metrics"
    metrics: AirportMetrics
    context: AirportContext | None = None


class ScoreResult(ResultBase):
    kind: Literal["score"] = "score"
    score: AirportScore
    context: AirportContext | None = None


class ComparisonRow(BaseModel, frozen=True):
    airport_code: IATA
    score: AirportScore
    metrics: AirportMetrics
    context: AirportContext | None = None


class ComparisonResult(ResultBase):
    kind: Literal["comparison"] = "comparison"
    rows: list[ComparisonRow]
    highest_congestion: str | None
    highest_opportunity_score: str | None
    period_warning: str | None


class RankingResult(ResultBase):
    kind: Literal["ranking"] = "ranking"
    ranked: list[AirportScore]
    region: str
    peer_note: str
    metric: str = "opportunity_score"


class DriverRow(BaseModel, frozen=True):
    name: str
    base_weight: float
    effective_weight: float
    normalized_contribution: float


class ExplainCongestionRow(BaseModel, frozen=True):
    airport_code: IATA
    congestion_score: DatumFloat
    drivers: list[DriverRow]
    highest_driver: str | None = None


class CongestionExplainResult(ResultBase):
    kind: Literal["congestion_explain"] = "congestion_explain"
    rows: list[ExplainCongestionRow]


class ExplainUnmetRow(BaseModel, frozen=True):
    airport_code: IATA
    unmet_demand_index: DatumFloat
    drivers: list[DriverRow]
    highest_driver: str | None = None


class UnmetExplainResult(ResultBase):
    kind: Literal["unmet_explain"] = "unmet_explain"
    rows: list[ExplainUnmetRow]


class ExplainCapacityRow(BaseModel, frozen=True):
    airport_code: IATA
    capacity_pressure_score: DatumFloat
    drivers: list[DriverRow]
    highest_driver: str | None = None
    pax_per_operation: DatumFloat | None = None


class CapacityExplainResult(ResultBase):
    kind: Literal["capacity_explain"] = "capacity_explain"
    rows: list[ExplainCapacityRow]


class LongHaulResult(ResultBase):
    kind: Literal["long_haul"] = "long_haul"
    long_haul_pct: DatumFloat
    basis: str | None = None
    threshold_statute_miles: float = 3000.0
    start_year: int | None = None
    end_year: int | None = None
    total_departures: float | None = None
    long_haul_departures: float | None = None
    passenger_only: bool = False
    passenger_only_filter_available: bool = True
    unique_destinations: int | None = None
    long_haul_destinations: int | None = None
    average_distance_miles: float | None = None
    max_distance_miles: float | None = None
    top_long_haul_routes: list[dict[str, Any]] = []
    source: str = "BTS T-100 Segment"
    calculation: str | None = None
    metadata: dict[str, Any] = {}


class UnmetDemandResult(ResultBase):
    kind: Literal["unmet_demand"] = "unmet_demand"
    unmet_demand_index: DatumFloat


class SimulationResult(ResultBase):
    kind: Literal["simulation"] = "simulation"
    baseline_score: AirportScore
    simulated_score: AirportScore
    growth_adjustment: float
    delta_opportunity: float | None


class ToolRejection(ResultBase):
    kind: Literal["rejection"] = "rejection"
    tool_name: str
    reason: str


ToolResult = Annotated[
    Union[
        MetricsResult,
        ScoreResult,
        ComparisonResult,
        RankingResult,
        LongHaulResult,
        UnmetDemandResult,
        SimulationResult,
        CongestionExplainResult,
        UnmetExplainResult,
        CapacityExplainResult,
        ToolRejection,
    ],
    Discriminator("kind"),
]


# ---------------------------------------------------------------------------
# Confirmation flow
# ---------------------------------------------------------------------------


class ConfirmOption(BaseModel, frozen=True):
    label: str
    value: str


class Confirmation(BaseModel, frozen=True):
    prompt: str
    options: list[ConfirmOption]


# ---------------------------------------------------------------------------
# Freshness / confidence helpers
# ---------------------------------------------------------------------------

_SCORE_DATUM_FIELDS: tuple[str, ...] = (
    "opportunity_score",
    "demand_growth_score",
    "congestion_score",
    "delay_pressure_score",
    "capacity_pressure_score",
)

_CONF_RANK: dict[Confidence, int] = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
_RANK_CONF: dict[int, Confidence] = {v: k for k, v in _CONF_RANK.items()}


def _min_confidence(scores: Iterable[AirportScore]) -> Confidence:
    worst = 2
    found = False
    for s in scores:
        found = True
        worst = min(worst, _CONF_RANK[s.confidence])
    if not found:
        return "LOW"
    return _RANK_CONF[worst]


def _resolve_freshness(
    scores: Iterable[AirportScore],
) -> Literal["live", "mixed", "sample"]:
    has_live = has_sample = False
    for s in scores:
        for fname in _SCORE_DATUM_FIELDS:
            datum = getattr(s, fname)
            if not isinstance(datum, Present):
                continue
            o = datum.origin
            if isinstance(o, Live):
                has_live = True
            elif isinstance(o, Sample):
                has_sample = True
            elif isinstance(o, (Derived, Proxy)):
                if o.freshness == "live":
                    has_live = True
                elif o.freshness == "sample":
                    has_sample = True
                else:
                    has_live = has_sample = True
    if has_live and has_sample:
        return "mixed"
    if has_sample:
        return "sample"
    return "live"


def _dedup(seq: list[str]) -> list[str]:
    return list(dict.fromkeys(seq))


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------


class ChatResponse(BaseModel):
    message: str
    airports: list[str]
    analysis_type: str | None = None
    scores: dict[str, AirportScore] = {}
    sources: list[str] = []
    assumptions: list[str] = []
    warnings: list[str] = []
    confidence: Confidence = "LOW"
    data_freshness: Literal["live", "mixed", "sample"] = "live"
    evidence: list[ToolResult] = []
    evidence_origin: Literal["this_turn", "carried", "none"] = "none"
    needs_confirmation: Confirmation | None = None

    @staticmethod
    def assemble(
        prose: str,
        evidence: list[ToolResult],
        origin: Literal["this_turn", "carried", "none"],
        extra_warnings: list[str] | None = None,
    ) -> ChatResponse:
        all_airports: list[str] = []
        scores: dict[str, AirportScore] = {}
        sources: list[str] = []
        assumptions: list[str] = []
        warnings: list[str] = []
        analysis_type: str | None = None

        for ev in evidence:
            all_airports.extend(ev.airports)

            if isinstance(ev, ToolRejection):
                warnings.append(f"Tool {ev.tool_name}: {ev.reason}")
                continue

            if analysis_type is None:
                analysis_type = ev.kind

            if isinstance(ev, ScoreResult):
                _collect_score(ev.score, scores, sources, assumptions, warnings)
                if ev.context:
                    warnings.extend(ev.context.warnings)

            elif isinstance(ev, ComparisonResult):
                for row in ev.rows:
                    _collect_score(row.score, scores, sources, assumptions, warnings)
                    _collect_metrics(row.metrics, row.context, sources, warnings)
                if ev.period_warning:
                    warnings.append(ev.period_warning)

            elif isinstance(ev, RankingResult):
                for s in ev.ranked:
                    _collect_score(s, scores, sources, assumptions, warnings)

            elif isinstance(ev, (CongestionExplainResult, UnmetExplainResult, CapacityExplainResult)):
                for row in ev.rows:
                    for attr in (
                        "congestion_score",
                        "unmet_demand_index",
                        "capacity_pressure_score",
                    ):
                        if hasattr(row, attr):
                            datum = getattr(row, attr)
                            if isinstance(datum, Present) and isinstance(datum.origin, Proxy):
                                assumptions.append(datum.origin.assumption)

            elif isinstance(ev, MetricsResult):
                _collect_metrics(ev.metrics, ev.context, sources, warnings)

            elif isinstance(ev, SimulationResult):
                _collect_score(ev.baseline_score, scores, sources, assumptions, warnings)

        if extra_warnings:
            warnings.extend(extra_warnings)

        return ChatResponse(
            message=prose,
            airports=_dedup(all_airports),
            analysis_type=analysis_type,
            scores=scores,
            sources=_dedup(sources),
            assumptions=_dedup(assumptions),
            warnings=_dedup(warnings),
            confidence=_min_confidence(scores.values()),
            data_freshness=_resolve_freshness(scores.values()),
            evidence=evidence,
            evidence_origin=origin,
            needs_confirmation=None,
        )


def _collect_score(
    s: AirportScore,
    scores: dict[str, AirportScore],
    sources: list[str],
    assumptions: list[str],
    warnings: list[str],
) -> None:
    scores[s.airport_code] = s
    sources.extend(s.sources)
    assumptions.extend(s.assumptions)
    warnings.extend(s.limitations)
    
def _collect_metrics(
    m: AirportMetrics,
    context: AirportContext | None,
    sources: list[str],
    warnings: list[str],
) -> None:
    sources.extend(m.sources)
    warnings.extend(m.warnings)
    if context:
        warnings.extend(context.warnings)
