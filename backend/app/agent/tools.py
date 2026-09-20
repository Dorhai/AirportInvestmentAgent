"""Approved LLM tools — thin projections over the Universe snapshot."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, NamedTuple, Literal
from datetime import datetime

from pydantic import BaseModel, ValidationError

from app.agent.llm import ToolCall
from app.models.airport import IATA, REGIONS, Region
from app.models.chat import (
    CapacityExplainResult,
    CongestionExplainResult,
    ComparisonResult,
    ComparisonRow,
    DriverRow,
    ExplainCapacityRow,
    ExplainCongestionRow,
    ExplainUnmetRow,
    LongHaulResult,
    MetricsResult,
    RankingResult,
    ScoreResult,
    SimulationResult,
    ToolRejection,
    ToolResult,
    UnmetDemandResult,
    UnmetExplainResult,
    DelayMetricsResult,
    DelayComparisonResult,
    DelayCausesResult,
    DelayTrendResult,
)
from app.analytics.drivers import (
    capacity_pressure_drivers,
    congestion_drivers,
    sort_scores_by_metric,
    unmet_demand_drivers,
)
from app.models.metrics import Absent, DatumFloat, Present
from app.scoring.expansion_score import rank
from app.services.analysis_service import GrowthPct, Universe

logger = logging.getLogger(__name__)

_METRIC_DISPLAY: dict[str, str] = {
    "opportunity_score": "opportunity score",
    "demand_growth_score": "demand growth score",
    "congestion_score": "congestion score",
    "delay_pressure_score": "delay pressure score",
    "capacity_pressure_score": "capacity pressure score",
    "passenger_growth": "passenger growth",
    "unmet_demand_index": "unmet demand index",
}


def _metric_display_label(metric: str) -> str:
    return _METRIC_DISPLAY.get(metric, metric.replace("_", " "))


# ---------------------------------------------------------------------------
# Arg models
# ---------------------------------------------------------------------------


class CodeArgs(BaseModel, frozen=True):
    code: IATA


class CodesArgs(BaseModel, frozen=True):
    codes: list[IATA]


class RegionArgs(BaseModel, frozen=True):
    region: Region


class MetricRankArgs(BaseModel, frozen=True):
    metric: str
    region: str = ""


class SimArgs(BaseModel, frozen=True):
    code: IATA
    growth_pct: float

class DateRangeArgs(BaseModel, frozen=True):
    code: IATA
    start_date: str | None = None
    end_date: str | None = None

class DirectionArgs(BaseModel, frozen=True):
    code: IATA
    direction: Literal["departures", "arrivals", "both"] = "both"

class DelayCompareArgs(BaseModel, frozen=True):
    airport_a: IATA
    airport_b: IATA
    start_date: str | None = None
    end_date: str | None = None


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class _ToolDef(NamedTuple):
    fn: Callable[..., ToolResult]
    args_model: type[BaseModel]
    description: str


TOOLS: dict[str, _ToolDef] = {}


def tool(
    name: str, *, args: type[BaseModel], description: str = ""
) -> Callable[[Callable[..., ToolResult]], Callable[..., ToolResult]]:
    def decorator(fn: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
        TOOLS[name] = _ToolDef(fn=fn, args_model=args, description=description)
        return fn

    return decorator


def tool_schemas(names: list[str] | None = None) -> list[dict[str, Any]]:
    """OpenAI-compatible function schemas for the requested tool names."""
    out: list[dict[str, Any]] = []
    for tname, defn in TOOLS.items():
        if names is not None and tname not in names:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tname,
                    "description": defn.description,
                    "parameters": defn.args_model.model_json_schema(),
                },
            }
        )
    return out


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def _rejection(
    name: str, snapshot: str, airports: list[str], reason: str
) -> ToolRejection:
    return ToolRejection(
        airports=airports,
        snapshot_at=snapshot,
        tool_name=name,
        reason=reason,
    )


def execute(call: ToolCall, u: Universe) -> ToolResult:
    defn = TOOLS.get(call.name)
    if defn is None:
        return _rejection(call.name, u.snapshot_at, [], f"Unknown tool: {call.name}")

    try:
        validated = defn.args_model(**call.arguments)
    except ValidationError as exc:
        return _rejection(call.name, u.snapshot_at, [], str(exc))

    try:
        return defn.fn(validated, u)
    except Exception as exc:
        logger.exception("Tool %s raised unexpectedly", call.name)
        return _rejection(call.name, u.snapshot_at, [], str(exc))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(
    "get_airport_metrics",
    args=CodeArgs,
    description="Retrieve raw traffic and delay metrics for one airport",
)
def get_airport_metrics(a: CodeArgs, u: Universe) -> ToolResult:
    dossier = u.dossiers.get(a.code)
    if dossier is None:
        return _rejection(
            "get_airport_metrics", u.snapshot_at, [a.code],
            f"Airport {a.code} not in universe",
        )
    return MetricsResult(
        airports=[a.code], snapshot_at=u.snapshot_at, metrics=dossier.metrics, context=dossier.context
    )


@tool(
    "get_airport_score",
    args=CodeArgs,
    description="Get the expansion opportunity score for one airport",
)
def get_airport_score(a: CodeArgs, u: Universe) -> ToolResult:
    score = u.scores.get(a.code)
    dossier = u.dossiers.get(a.code)
    if score is None or dossier is None:
        return _rejection(
            "get_airport_score", u.snapshot_at, [a.code],
            f"Airport {a.code} not in universe",
        )
    return ScoreResult(
        airports=[a.code], snapshot_at=u.snapshot_at, score=score, context=dossier.context
    )


@tool(
    "compare_airports",
    args=CodesArgs,
    description="Side-by-side comparison of two or more airports",
)
def compare_airports(a: CodesArgs, u: Universe) -> ToolResult:
    codes_list = list(a.codes)
    rows: list[ComparisonRow] = []
    for code in a.codes:
        score = u.scores.get(code)
        dossier = u.dossiers.get(code)
        if score is None or dossier is None:
            return _rejection(
                "compare_airports", u.snapshot_at, codes_list,
                f"Airport {code} not in universe",
            )
        rows.append(
            ComparisonRow(
                airport_code=code, score=score, metrics=dossier.metrics, context=dossier.context
            )
        )

    best_cong: float = -1.0
    best_opp: float = -1.0
    highest_congestion: str | None = None
    highest_opportunity: str | None = None
    for row in rows:
        if (
            isinstance(row.score.congestion_score, Present)
            and row.score.congestion_score.value > best_cong
        ):
            best_cong = row.score.congestion_score.value
            highest_congestion = row.airport_code
        if (
            isinstance(row.score.opportunity_score, Present)
            and row.score.opportunity_score.value > best_opp
        ):
            best_opp = row.score.opportunity_score.value
            highest_opportunity = row.airport_code

    periods = {row.metrics.data_period for row in rows}
    period_warning = (
        "Data periods differ across airports" if len(periods) > 1 else None
    )

    return ComparisonResult(
        airports=codes_list,
        snapshot_at=u.snapshot_at,
        rows=rows,
        highest_congestion=highest_congestion,
        highest_opportunity_score=highest_opportunity,
        period_warning=period_warning,
    )


@tool(
    "rank_airports",
    args=CodesArgs,
    description="Rank specified airports by opportunity score",
)
def rank_airports(a: CodesArgs, u: Universe) -> ToolResult:
    codes_list = list(a.codes)
    scores = []
    for code in a.codes:
        s = u.scores.get(code)
        if s is None:
            return _rejection(
                "rank_airports", u.snapshot_at, codes_list,
                f"Airport {code} not in universe",
            )
        scores.append(s)
    ranked = rank(scores)
    return RankingResult(
        airports=codes_list,
        snapshot_at=u.snapshot_at,
        ranked=ranked,
        region="",
        peer_note=f"Ranked {len(ranked)} of {len(u.scores)} universe airports",
    )


@tool(
    "rank_region",
    args=RegionArgs,
    description="Rank all airports in a geographic region",
)
def rank_region(a: RegionArgs, u: Universe) -> ToolResult:
    states = REGIONS.get(a.region)
    if states is None:
        return _rejection(
            "rank_region", u.snapshot_at, [],
            f"Unknown region: {a.region}",
        )

    region_codes_set: set[str] = set()
    if u.catalog is not None:
        region_codes_set = set(u.catalog.get_cached_region_codes(a.region))

    region_scores = []
    for code, dossier in u.dossiers.items():
        in_region = dossier.airport.state in states or code in region_codes_set
        if not in_region:
            continue
        s = u.scores.get(code)
        if s is not None:
            region_scores.append(s)

    if not region_scores:
        return _rejection(
            "rank_region", u.snapshot_at, [],
            f"No airports in {a.region} have complete BTS T-100 data",
        )

    ranked = rank(region_scores)
    airports = [s.airport_code for s in ranked]
    return RankingResult(
        airports=airports,
        snapshot_at=u.snapshot_at,
        ranked=ranked,
        region=a.region,
        peer_note=f"{len(ranked)} airports in {a.region}",
    )


@tool(
    "get_long_haul_percentage",
    args=CodeArgs,
    description="Long-haul flight percentage for one airport",
)
def get_long_haul_percentage(a: CodeArgs, u: Universe) -> ToolResult:
    dossier = u.dossiers.get(a.code)
    if dossier is None:
        return _rejection(
            "get_long_haul_percentage", u.snapshot_at, [a.code],
            f"Airport {a.code} not in universe",
        )
    
    kwargs = {
        "airports": [a.code],
        "snapshot_at": u.snapshot_at,
        "long_haul_pct": dossier.long_haul_pct,
    }
    
    if dossier.long_haul_summary:
        s = dossier.long_haul_summary
        kwargs.update({
            "total_departures": s.total_departures,
            "long_haul_departures": s.long_haul_departures,
            "unique_destinations": s.unique_destinations,
            "long_haul_destinations": s.long_haul_destinations,
            "average_distance_miles": s.average_distance_miles,
            "max_distance_miles": s.max_distance_miles,
            "top_long_haul_routes": s.top_long_haul_routes,
            "start_year": s.start_year,
            "end_year": s.end_year,
            "calculation": "long_haul_departures / total_departures * 100",
            "source": "BTS T-100 Segment (bulk file)",
            "metadata": {},
        })
        if isinstance(dossier.long_haul_pct, Present):
            kwargs["metadata"]["segment_file_period"] = getattr(dossier.long_haul_pct.origin, "period", None)

    # Attach live proxies
    intl = dossier.metrics.international_departures
    total = dossier.metrics.total_departures
    avg_dist = dossier.metrics.average_flight_distance_sm
    
    basis_parts = []
    if dossier.long_haul_summary and isinstance(dossier.long_haul_pct, Present):
        basis_parts.append(f"Long-haul from bulk file ({getattr(dossier.long_haul_pct.origin, 'period', 'unknown')})")
    
    if isinstance(intl, Present) and isinstance(total, Present) and total.value > 0:
        kwargs["international_departures"] = float(intl.value)
        kwargs["international_departure_share_pct"] = (intl.value / total.value) * 100.0
        live_period = getattr(intl.origin, "period", "unknown")
        kwargs["live_period"] = live_period
        basis_parts.append(f"Live proxies ({live_period})")
        
    if isinstance(avg_dist, Present):
        kwargs["live_average_distance_miles"] = float(avg_dist.value)
        
    if basis_parts:
        kwargs["basis"] = "; ".join(basis_parts)
        
    return LongHaulResult(**kwargs)


@tool(
    "get_unmet_demand",
    args=CodeArgs,
    description="Unmet demand index for one airport",
)
def get_unmet_demand(a: CodeArgs, u: Universe) -> ToolResult:
    dossier = u.dossiers.get(a.code)
    if dossier is None:
        return _rejection(
            "get_unmet_demand", u.snapshot_at, [a.code],
            f"Airport {a.code} not in universe",
        )
    return UnmetDemandResult(
        airports=[a.code],
        snapshot_at=u.snapshot_at,
        unmet_demand_index=dossier.unmet_demand_index,
    )


@tool(
    "simulate_airport_growth",
    args=SimArgs,
    description="Simulate how a demand-growth change affects the score",
)
def simulate_airport_growth(a: SimArgs, u: Universe) -> ToolResult:
    try:
        sim = u.simulate(a.code, GrowthPct(a.growth_pct))
    except ValueError as exc:
        return _rejection(
            "simulate_airport_growth", u.snapshot_at, [a.code], str(exc)
        )
    return SimulationResult(
        airports=[a.code],
        snapshot_at=u.snapshot_at,
        baseline_score=sim.baseline_score,
        simulated_score=sim.simulated_score,
        growth_adjustment=sim.growth_adjustment,
        delta_opportunity=sim.delta_opportunity,
    )


def _driver_rows(breakdown) -> list[DriverRow]:
    return [
        DriverRow(
            name=d.name,
            base_weight=d.base_weight,
            effective_weight=d.effective_weight,
            normalized_contribution=d.normalized_contribution,
        )
        for d in breakdown.drivers
    ]


@tool(
    "explain_congestion",
    args=CodesArgs,
    description="Congestion proxy score and driver breakdown for one or more airports",
)
def explain_congestion(a: CodesArgs, u: Universe) -> ToolResult:
    rows: list[ExplainCongestionRow] = []
    codes_list = list(a.codes)
    for code in a.codes:
        dossier = u.dossiers.get(code)
        if dossier is None:
            return _rejection(
                "explain_congestion", u.snapshot_at, codes_list,
                f"Airport {code} not in universe",
            )
        gdp = bool(dossier.context.nas_delay_program)
        breakdown = congestion_drivers(dossier.metrics, u.peers, gdp_active=gdp)
        rows.append(
            ExplainCongestionRow(
                airport_code=code,
                congestion_score=breakdown.score,
                drivers=_driver_rows(breakdown),
                highest_driver=breakdown.highest_driver,
            )
        )
    return CongestionExplainResult(
        airports=codes_list, snapshot_at=u.snapshot_at, rows=rows
    )


@tool(
    "explain_unmet_demand",
    args=CodeArgs,
    description="Unmet demand index and weighted driver breakdown for one airport",
)
def explain_unmet_demand(a: CodeArgs, u: Universe) -> ToolResult:
    dossier = u.dossiers.get(a.code)
    score = u.scores.get(a.code)
    if dossier is None or score is None:
        return _rejection(
            "explain_unmet_demand", u.snapshot_at, [a.code],
            f"Airport {a.code} not in universe",
        )
    breakdown = unmet_demand_drivers(
        dossier.passenger_growth,
        score.delay_pressure_score,
        score.congestion_score,
        u.peers,
    )
    return UnmetExplainResult(
        airports=[a.code],
        snapshot_at=u.snapshot_at,
        rows=[
            ExplainUnmetRow(
                airport_code=a.code,
                unmet_demand_index=breakdown.score,
                drivers=_driver_rows(breakdown),
                highest_driver=breakdown.highest_driver,
            )
        ],
    )


@tool(
    "explain_capacity_pressure",
    args=CodesArgs,
    description="Capacity pressure proxy and drivers (pax per operation vs growth)",
)
def explain_capacity_pressure(a: CodesArgs, u: Universe) -> ToolResult:
    rows: list[ExplainCapacityRow] = []
    codes_list = list(a.codes)
    for code in a.codes:
        dossier = u.dossiers.get(code)
        score = u.scores.get(code)
        if dossier is None or score is None:
            return _rejection(
                "explain_capacity_pressure", u.snapshot_at, codes_list,
                f"Airport {code} not in universe",
            )
        breakdown = capacity_pressure_drivers(
            dossier.metrics, dossier.passenger_growth, u.peers
        )
        pax_per_op: DatumFloat | None = None
        pax = dossier.metrics.passenger_volume
        ops = dossier.metrics.annual_operations
        if isinstance(pax, Present) and isinstance(ops, Present) and ops.value > 0:
            from app.models.metrics import fold_origins

            val = pax.value / ops.value
            pax_per_op = Present[float](
                value=val,
                origin=fold_origins(
                    pax.origin, ops.origin, method="pax_per_operation"
                ),
            )
        rows.append(
            ExplainCapacityRow(
                airport_code=code,
                capacity_pressure_score=breakdown.score,
                drivers=_driver_rows(breakdown),
                highest_driver=breakdown.highest_driver,
                pax_per_operation=pax_per_op,
            )
        )
    return CapacityExplainResult(
        airports=codes_list, snapshot_at=u.snapshot_at, rows=rows
    )


@tool(
    "rank_by_metric",
    args=MetricRankArgs,
    description="Rank peer airports by a score or growth metric, optionally within a region",
)
def rank_by_metric(a: MetricRankArgs, u: Universe) -> ToolResult:
    metric = a.metric.strip()
    allowed = {
        "opportunity_score",
        "demand_growth_score",
        "congestion_score",
        "delay_pressure_score",
        "capacity_pressure_score",
        "passenger_growth",
        "unmet_demand_index",
    }
    if metric not in allowed:
        return _rejection(
            "rank_by_metric", u.snapshot_at, [],
            f"Unknown metric: {metric}. Allowed: {', '.join(sorted(allowed))}",
        )

    codes: list[str] = []
    if a.region:
        states = REGIONS.get(a.region)  # type: ignore[arg-type]
        if states is None:
            return _rejection(
                "rank_by_metric", u.snapshot_at, [],
                f"Unknown region: {a.region}",
            )
        for code, dossier in u.dossiers.items():
            if dossier.airport.state in states:
                codes.append(code)
    else:
        codes = list(u.dossiers.keys())

    if not codes:
        return _rejection("rank_by_metric", u.snapshot_at, [], "No airports to rank")

    if metric in ("passenger_growth", "unmet_demand_index"):
        sorted_codes = sorted(
            codes,
            key=lambda c: (
                0
                if isinstance(
                    (
                        u.dossiers[c].passenger_growth
                        if metric == "passenger_growth"
                        else u.dossiers[c].unmet_demand_index
                    ),
                    Present,
                )
                else 1,
                -(
                    (
                        u.dossiers[c].passenger_growth.value  # type: ignore[union-attr]
                        if metric == "passenger_growth"
                        else u.dossiers[c].unmet_demand_index.value  # type: ignore[union-attr]
                    )
                    if isinstance(
                        (
                            u.dossiers[c].passenger_growth
                            if metric == "passenger_growth"
                            else u.dossiers[c].unmet_demand_index
                        ),
                        Present,
                    )
                    else 0.0
                ),
            ),
        )
        ranked_scores = [u.scores[c] for c in sorted_codes if c in u.scores]
    else:
        pool = [u.scores[c] for c in codes if c in u.scores]
        ranked_scores = sort_scores_by_metric(pool, metric)

    airports = [s.airport_code for s in ranked_scores]
    region_label = a.region or "peer_universe"
    return RankingResult(
        airports=airports,
        snapshot_at=u.snapshot_at,
        ranked=ranked_scores,
        region=region_label,
        peer_note=(
            f"Ranked by {_metric_display_label(metric)} ({len(ranked_scores)} airports)"
        ),
        metric=metric,
    )

def _parse_date(d_str: str | None) -> date | None:
    if not d_str:
        return None
    try:
        if "-" in d_str:
            return datetime.strptime(d_str.split(" ")[0], "%Y-%m-%d").date()
        else:
            return datetime.strptime(d_str.split(" ")[0], "%m/%d/%Y").date()
    except ValueError:
        return None

@tool(
    "get_bts_delay_metrics",
    args=DirectionArgs,
    description="Retrieve historical delay metrics (departure/arrival) for an airport from BTS On-Time data",
)
def get_bts_delay_metrics(a: DirectionArgs, u: Universe) -> ToolResult:
    if not u.ontime_service or not u.ontime_service.is_loaded:
        return _rejection("get_bts_delay_metrics", u.snapshot_at, [a.code], "BTS On-Time service not loaded")
        
    metrics = u.ontime_service.get_airport_delay_metrics(a.code, direction=a.direction)
    if not metrics:
        return _rejection("get_bts_delay_metrics", u.snapshot_at, [a.code], "No delay metrics found")
        
    return DelayMetricsResult(airports=[a.code], snapshot_at=u.snapshot_at, metrics=metrics)

@tool(
    "compare_bts_airport_delays",
    args=DelayCompareArgs,
    description="Compare historical delay metrics between two airports using BTS On-Time data",
)
def compare_bts_airport_delays(a: DelayCompareArgs, u: Universe) -> ToolResult:
    if not u.ontime_service or not u.ontime_service.is_loaded:
        return _rejection("compare_bts_airport_delays", u.snapshot_at, [a.airport_a, a.airport_b], "BTS On-Time service not loaded")
        
    start_d = _parse_date(a.start_date)
    end_d = _parse_date(a.end_date)
    
    comp = u.ontime_service.compare_airport_delays(a.airport_a, a.airport_b, start_date=start_d, end_date=end_d)
    if not comp:
        return _rejection("compare_bts_airport_delays", u.snapshot_at, [a.airport_a, a.airport_b], "No delay metrics found for comparison")
        
    return DelayComparisonResult(airports=[a.airport_a, a.airport_b], snapshot_at=u.snapshot_at, comparison=comp)

@tool(
    "get_bts_delay_causes",
    args=DirectionArgs,
    description="Retrieve breakdown of delay causes (Carrier, Weather, NAS, Security, LateAircraft) for an airport",
)
def get_bts_delay_causes(a: DirectionArgs, u: Universe) -> ToolResult:
    if not u.ontime_service or not u.ontime_service.is_loaded:
        return _rejection("get_bts_delay_causes", u.snapshot_at, [a.code], "BTS On-Time service not loaded")
        
    causes = u.ontime_service.get_delay_causes(a.code, direction=a.direction if a.direction in ("departures", "arrivals") else "departures")
    if not causes:
        return _rejection("get_bts_delay_causes", u.snapshot_at, [a.code], "No delay causes found")
        
    return DelayCausesResult(airports=[a.code], snapshot_at=u.snapshot_at, causes=causes)

@tool(
    "get_bts_delay_trend",
    args=DirectionArgs,
    description="Retrieve monthly trend of delay percentages and minutes for an airport",
)
def get_bts_delay_trend(a: DirectionArgs, u: Universe) -> ToolResult:
    if not u.ontime_service or not u.ontime_service.is_loaded:
        return _rejection("get_bts_delay_trend", u.snapshot_at, [a.code], "BTS On-Time service not loaded")
        
    trend = u.ontime_service.get_delay_trend(a.code, direction=a.direction if a.direction in ("departures", "arrivals") else "departures")
    if not trend:
        return _rejection("get_bts_delay_trend", u.snapshot_at, [a.code], "No delay trend found")
        
    return DelayTrendResult(airports=[a.code], snapshot_at=u.snapshot_at, airport=a.code, direction=a.direction, trend=trend)
