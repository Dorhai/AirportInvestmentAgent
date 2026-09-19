from __future__ import annotations

from app.analytics.capacity import calculate_capacity_pressure
from app.analytics.congestion import calculate_congestion_score, calculate_delay_pressure
from app.models.metrics import (
    Absent,
    AirportDossier,
    AirportMetrics,
    DatumFloat,
    Present,
    Proxy,
    fold_origins,
)
from app.models.score import (
    AirportScore,
    Confidence,
    PeerStats,
    ProviderFailure,
)
from app.scoring.normalization import clamp_score, normalize_min_max

# ------------------------------------------------------------------
# Canonical weights — the ONLY place these live
# ------------------------------------------------------------------

SCORING_WEIGHTS: dict[str, float] = {
    "demand_growth": 0.30,
    "congestion": 0.30,
    "delay_pressure": 0.20,
    "capacity_pressure": 0.20,
}
assert abs(sum(SCORING_WEIGHTS.values()) - 1.0) < 1e-9, (
    "scoring weights must sum to 1.0"
)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _normalize_datum(
    datum: DatumFloat, key: str, peers: PeerStats
) -> DatumFloat:
    """Scale a raw analytical value to a 0–100 score using peer bounds."""
    if isinstance(datum, Absent):
        return datum
    lo, hi = peers.bounds.get(key, (0.0, 1.0))
    score = clamp_score(normalize_min_max(datum.value, lo, hi))
    origin = fold_origins(
        datum.origin,
        method=f"{key}_score",
        proxy=True,
        assumption=f"Normalized {key} against peer bounds",
    )
    return Present[float](value=score, origin=origin)


def _weighted_opportunity(components: dict[str, DatumFloat]) -> DatumFloat:
    """Combine component scores using ``SCORING_WEIGHTS``.

    If some components are absent their weights are redistributed across
    the present ones.  If all are absent the result is absent.
    """
    present: list[tuple[str, float, Present[float]]] = []
    absent_attempted: list[str] = []

    for key, datum in components.items():
        if isinstance(datum, Present):
            present.append((key, SCORING_WEIGHTS[key], datum))
        elif isinstance(datum, Absent):
            absent_attempted.extend(datum.attempted)

    if not present:
        return Absent(
            reason="NOT_PUBLISHED",
            detail="all scoring components absent",
            attempted=tuple(dict.fromkeys(absent_attempted)),
        )

    total_weight = sum(w for _, w, _ in present)
    raw = sum(w / total_weight * d.value for _, w, d in present)
    score = clamp_score(raw)

    origin = fold_origins(
        *(d.origin for _, _, d in present),
        method="expansion_opportunity_score",
        proxy=True,
        assumption="Weighted combination of demand, congestion, delay, and capacity scores",
    )
    return Present[float](value=score, origin=origin)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def score_dossier(
    d: AirportDossier,
    peers: PeerStats,
) -> AirportScore:
    """Deterministic scoring of a fully-assembled dossier."""
    demand = _normalize_datum(d.passenger_growth, "demand_growth", peers)

    congestion = calculate_congestion_score(
        d.metrics, peers, gdp_active=bool(d.context.nas_delay_program)
    )

    delay = calculate_delay_pressure(
        d.metrics.delayed_flights_pct,
        d.metrics.average_delay_minutes,
    )

    capacity = calculate_capacity_pressure(d.metrics, d.passenger_growth, peers)

    components: dict[str, DatumFloat] = {
        "demand_growth": demand,
        "congestion": congestion,
        "delay_pressure": delay,
        "capacity_pressure": capacity,
    }

    opportunity = _weighted_opportunity(components)
    confidence = calculate_confidence(d.metrics, components)

    return AirportScore(
        airport_code=d.airport.iata_code,
        airport_name=d.airport.name,
        opportunity_score=opportunity,
        demand_growth_score=demand,
        congestion_score=congestion,
        delay_pressure_score=delay,
        capacity_pressure_score=capacity,
        confidence=confidence,
        context=d.context,
        snapshot_at=d.snapshot_at,
    )


def calculate_confidence(
    m: AirportMetrics,
    components: dict[str, DatumFloat],
) -> Confidence:
    """HIGH when core data is near-complete and all score components are present,
    LOW when sparse or missing multiple score components."""
    completeness = m.core_completeness_score
    present_count = sum(
        1 for d in components.values() if isinstance(d, Present)
    )
    total = len(components)
    component_ratio = present_count / total if total else 0.0

    if completeness >= 1.0 and component_ratio >= 1.0:
        return "HIGH"

    if completeness < 0.8 or present_count < 3:
        return "LOW"

    return "MEDIUM"


def rank(scores: list[AirportScore]) -> list[AirportScore]:
    """Return *scores* ordered by opportunity score descending.

    Airports with absent opportunity scores sort to the end.
    """

    def _key(s: AirportScore) -> tuple[int, float]:
        if isinstance(s.opportunity_score, Present):
            return (0, -s.opportunity_score.value)
        return (1, 0.0)

    return sorted(scores, key=_key)


def compare(
    a: AirportScore, b: AirportScore
) -> dict[str, float | None]:
    """Per-component delta (a − b).  ``None`` when either side is absent."""
    fields = (
        "opportunity_score",
        "demand_growth_score",
        "congestion_score",
        "delay_pressure_score",
        "capacity_pressure_score",
    )
    result: dict[str, float | None] = {}
    for field in fields:
        da = getattr(a, field)
        db = getattr(b, field)
        if isinstance(da, Present) and isinstance(db, Present):
            result[field] = round(da.value - db.value, 1)
        else:
            result[field] = None
    return result
