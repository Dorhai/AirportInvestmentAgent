"""Deterministic driver breakdowns for proxy scores (mirrors score formulas)."""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.congestion import calculate_congestion_score
from app.analytics.capacity import calculate_capacity_pressure
from app.analytics.opportunity import calculate_unmet_demand_index
from app.models.metrics import (
    Absent,
    AirportMetrics,
    DatumFloat,
    Present,
)
from app.models.score import AirportScore, PeerStats
from app.scoring.normalization import clamp_score, normalize_min_max, normalize_percentage


@dataclass(frozen=True)
class ScoreDriver:
    name: str
    base_weight: float
    effective_weight: float
    normalized_contribution: float


@dataclass(frozen=True)
class DriverBreakdown:
    score: DatumFloat
    drivers: tuple[ScoreDriver, ...]
    highest_driver: str | None


def _highest(drivers: tuple[ScoreDriver, ...]) -> str | None:
    present = [d for d in drivers if d.effective_weight > 0]
    if not present:
        return None
    top = max(present, key=lambda d: d.normalized_contribution * d.effective_weight)
    return top.name


def congestion_drivers(
    metrics: AirportMetrics,
    peers: PeerStats,
    *,
    gdp_active: bool = False,
) -> DriverBreakdown:
    """Mirror ``calculate_congestion_score`` component weights."""
    raw_components: list[tuple[str, float, float | None]] = []

    ops = metrics.annual_operations
    if isinstance(ops, Present):
        lo, hi = peers.bounds.get("annual_operations", (0.0, 1.0))
        raw_components.append(
            ("annual_operations", 0.5, normalize_min_max(float(ops.value), lo, hi))
        )
    else:
        raw_components.append(("annual_operations", 0.5, None))

    delayed = metrics.delayed_flights_pct
    if isinstance(delayed, Present):
        raw_components.append(
            ("delayed_flights_pct", 0.3, normalize_percentage(delayed.value))
        )
    else:
        raw_components.append(("delayed_flights_pct", 0.3, None))

    pax = metrics.passenger_volume
    if isinstance(pax, Present):
        lo, hi = peers.bounds.get("passenger_volume", (0.0, 1.0))
        raw_components.append(
            ("passenger_volume", 0.2, normalize_min_max(float(pax.value), lo, hi))
        )
    else:
        raw_components.append(("passenger_volume", 0.2, None))

    present = [(n, w, s) for n, w, s in raw_components if s is not None]
    total_w = sum(w for _, w, _ in present) if present else 0.0

    drivers: list[ScoreDriver] = []
    for name, base_w, score in raw_components:
        if score is None or total_w <= 0:
            drivers.append(
                ScoreDriver(name, base_w, 0.0, 0.0)
            )
        else:
            eff = base_w / total_w
            drivers.append(ScoreDriver(name, base_w, eff, score))

    score = calculate_congestion_score(metrics, peers, gdp_active=gdp_active)
    if gdp_active and isinstance(score, Present):
        score = Present[float](
            value=clamp_score(min(100.0, score.value)),
            origin=score.origin,
        )

    return DriverBreakdown(
        score=score,
        drivers=tuple(drivers),
        highest_driver=_highest(tuple(drivers)),
    )


def unmet_demand_drivers(
    growth: DatumFloat,
    delay: DatumFloat,
    congestion: DatumFloat,
    peers: PeerStats,
) -> DriverBreakdown:
    """Mirror ``calculate_unmet_demand_index`` weights."""
    raw: list[tuple[str, float, float | None]] = []

    if isinstance(growth, Present):
        lo, hi = peers.bounds.get("demand_growth", (0.0, 1.0))
        raw.append(("passenger_growth", 0.50, normalize_min_max(growth.value, lo, hi)))
    else:
        raw.append(("passenger_growth", 0.50, None))

    if isinstance(delay, Present):
        raw.append(("delay_pressure", 0.25, delay.value))
    else:
        raw.append(("delay_pressure", 0.25, None))

    if isinstance(congestion, Present):
        raw.append(("congestion_score", 0.25, congestion.value))
    else:
        raw.append(("congestion_score", 0.25, None))

    present = [(n, w, s) for n, w, s in raw if s is not None]
    total_w = sum(w for _, w, _ in present) if present else 0.0

    drivers: list[ScoreDriver] = []
    for name, base_w, val in raw:
        if val is None or total_w <= 0:
            drivers.append(ScoreDriver(name, base_w, 0.0, 0.0))
        else:
            eff = base_w / total_w
            drivers.append(ScoreDriver(name, base_w, eff, val))

    score = calculate_unmet_demand_index(growth, delay, congestion, peers)
    return DriverBreakdown(
        score=score,
        drivers=tuple(drivers),
        highest_driver=_highest(tuple(drivers)),
    )


def capacity_pressure_drivers(
    metrics: AirportMetrics,
    growth: DatumFloat,
    peers: PeerStats,
) -> DriverBreakdown:
    """Mirror ``calculate_capacity_pressure`` (utilisation vs growth)."""
    pax = metrics.passenger_volume
    ops = metrics.annual_operations
    util: float | None = None
    if isinstance(pax, Present) and isinstance(ops, Present) and ops.value > 0:
        pax_per_op = pax.value / ops.value
        lo, hi = peers.bounds.get(
            "pax_per_operation", (0.0, max(pax_per_op * 2, 1.0))
        )
        util = normalize_min_max(pax_per_op, lo, hi)

    growth_val: float | None = None
    if isinstance(growth, Present):
        growth_val = clamp_score(growth.value * 100.0)

    raw: list[tuple[str, float, float | None]] = [
        ("pax_per_operation", 0.6, util),
        ("passenger_growth", 0.4, growth_val),
    ]
    if growth_val is None:
        raw = [("pax_per_operation", 1.0, util)]

    present = [(n, w, s) for n, w, s in raw if s is not None]
    total_w = sum(w for _, w, _ in present) if present else 0.0

    drivers: list[ScoreDriver] = []
    for name, base_w, val in raw:
        if val is None or total_w <= 0:
            drivers.append(ScoreDriver(name, base_w, 0.0, 0.0))
        else:
            eff = base_w / total_w
            drivers.append(ScoreDriver(name, base_w, eff, val))

    score = calculate_capacity_pressure(metrics, growth, peers)
    return DriverBreakdown(
        score=score,
        drivers=tuple(drivers),
        highest_driver=_highest(tuple(drivers)),
    )


_METRIC_SCORE_FIELDS: dict[str, str] = {
    "opportunity_score": "opportunity_score",
    "demand_growth_score": "demand_growth_score",
    "congestion_score": "congestion_score",
    "delay_pressure_score": "delay_pressure_score",
    "capacity_pressure_score": "capacity_pressure_score",
}


def sort_scores_by_metric(
    scores: list[AirportScore], metric: str
) -> list[AirportScore]:
    field = _METRIC_SCORE_FIELDS.get(metric, metric)

    def _key(s: AirportScore) -> tuple[int, float]:
        datum = getattr(s, field, None)
        if isinstance(datum, Present):
            return (0, -datum.value)
        return (1, 0.0)

    return sorted(scores, key=_key)


def sort_dossiers_by_dossier_metric(
    entries: list[tuple[str, DatumFloat]],
) -> list[tuple[str, DatumFloat]]:
    def _key(item: tuple[str, DatumFloat]) -> tuple[int, float]:
        _, d = item
        if isinstance(d, Present):
            return (0, -d.value)
        return (1, 0.0)

    return sorted(entries, key=_key)
