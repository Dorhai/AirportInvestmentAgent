from __future__ import annotations

from app.models.metrics import (
    Absent,
    AirportMetrics,
    DatumFloat,
    Origin,
    Present,
    fold_origins,
)
from app.models.score import PeerStats
from app.scoring.normalization import clamp_score, normalize_min_max, normalize_percentage


def _collect_attempted(*datums: DatumFloat) -> tuple[str, ...]:
    parts: list[str] = []
    for d in datums:
        if isinstance(d, Absent):
            parts.extend(d.attempted)
    return tuple(dict.fromkeys(parts))


# ------------------------------------------------------------------
# Delay pressure
# ------------------------------------------------------------------


def calculate_delay_pressure(
    delayed_pct: DatumFloat,
    avg_delay_min: DatumFloat,
) -> DatumFloat:
    """``0.6 * pct_norm + 0.4 * delay_norm``.

    When one input is absent the other carries full weight and the
    renormalisation is recorded in the origin method string.
    """
    if isinstance(delayed_pct, Absent) and isinstance(avg_delay_min, Absent):
        return Absent(
            reason="NOT_PUBLISHED",
            detail="both delay metrics absent",
            attempted=_collect_attempted(delayed_pct, avg_delay_min),
        )

    if isinstance(delayed_pct, Absent):
        val = clamp_score(avg_delay_min.value / 60.0 * 100.0)  # type: ignore[union-attr]
        origin = fold_origins(
            avg_delay_min.origin,  # type: ignore[union-attr]
            method="delay_pressure (renormalized: delayed_pct absent)",
        )
        return Present[float](value=val, origin=origin)

    if isinstance(avg_delay_min, Absent):
        val = normalize_percentage(delayed_pct.value)  # type: ignore[union-attr]
        origin = fold_origins(
            delayed_pct.origin,  # type: ignore[union-attr]
            method="delay_pressure (renormalized: avg_delay_min absent)",
        )
        return Present[float](value=val, origin=origin)

    pct_norm = normalize_percentage(delayed_pct.value)
    delay_norm = clamp_score(avg_delay_min.value / 60.0 * 100.0)
    val = 0.6 * pct_norm + 0.4 * delay_norm
    origin = fold_origins(
        delayed_pct.origin, avg_delay_min.origin, method="delay_pressure"
    )
    return Present[float](value=val, origin=origin)


# ------------------------------------------------------------------
# Congestion score
# ------------------------------------------------------------------


def calculate_congestion_score(
    metrics: AirportMetrics,
    peers: PeerStats,
    gdp_active: bool = False,
) -> DatumFloat:
    """Proxy congestion indicator.

    ``0.5 * ops_norm + 0.3 * delayed_norm + 0.2 * pax_norm + (10 if gdp)``
    clamped to 0–100.  Absent inputs are dropped and remaining weights
    renormalised.
    """
    components: list[tuple[float, float]] = []
    origins_list: list[Origin] = []
    absent_attempted: list[str] = []

    ops = metrics.annual_operations
    if isinstance(ops, Present):
        lo, hi = peers.bounds.get("annual_operations", (0.0, 1.0))
        components.append((0.5, normalize_min_max(float(ops.value), lo, hi)))
        origins_list.append(ops.origin)
    elif isinstance(ops, Absent):
        absent_attempted.extend(ops.attempted)

    delayed = metrics.delayed_flights_pct
    if isinstance(delayed, Present):
        components.append((0.3, normalize_percentage(delayed.value)))
        origins_list.append(delayed.origin)
    elif isinstance(delayed, Absent):
        absent_attempted.extend(delayed.attempted)

    pax = metrics.passenger_volume
    if isinstance(pax, Present):
        lo, hi = peers.bounds.get("passenger_volume", (0.0, 1.0))
        components.append((0.2, normalize_min_max(float(pax.value), lo, hi)))
        origins_list.append(pax.origin)
    elif isinstance(pax, Absent):
        absent_attempted.extend(pax.attempted)

    if not components:
        return Absent(
            reason="NOT_PUBLISHED",
            detail="all congestion inputs absent",
            attempted=tuple(dict.fromkeys(absent_attempted)),
        )

    total_weight = sum(w for w, _ in components)
    raw = sum(w / total_weight * s for w, s in components)
    raw += 10.0 if gdp_active else 0.0
    score = clamp_score(max(0.0, min(100.0, raw)))

    origin = fold_origins(
        *origins_list,
        method="congestion_score",
        proxy=True,
        assumption="Congestion proxy from operations volume, delay rates, and passenger throughput",
    )
    return Present[float](value=score, origin=origin)
