from __future__ import annotations

from app.models.metrics import (
    Absent,
    AirportMetrics,
    DatumFloat,
    Present,
    fold_origins,
)
from app.models.score import PeerStats
from app.scoring.normalization import clamp_score, normalize_min_max


def calculate_capacity_pressure(
    metrics: AirportMetrics,
    growth: DatumFloat,
    peers: PeerStats,
) -> DatumFloat:
    """Proxy: normalised passengers-per-operation blended with growth.

    ``0.6 * utilisation_norm + 0.4 * growth_component`` when growth is
    present; falls back to utilisation alone otherwise.
    """
    pax = metrics.passenger_volume
    ops = metrics.annual_operations

    if isinstance(pax, Absent) or isinstance(ops, Absent):
        attempted: list[str] = []
        if isinstance(pax, Absent):
            attempted.extend(pax.attempted)
        if isinstance(ops, Absent):
            attempted.extend(ops.attempted)
        return Absent(
            reason="NOT_PUBLISHED",
            detail="passenger volume or operations absent",
            attempted=tuple(dict.fromkeys(attempted)),
        )

    if ops.value <= 0:
        return Absent(
            reason="OUT_OF_SCOPE",
            detail="annual operations <= 0",
            attempted=(),
        )

    pax_per_op = pax.value / ops.value
    lo, hi = peers.bounds.get(
        "pax_per_operation", (0.0, max(pax_per_op * 2, 1.0))
    )
    utilisation_score = normalize_min_max(pax_per_op, lo, hi)

    origins = [pax.origin, ops.origin]

    if isinstance(growth, Present):
        growth_component = clamp_score(growth.value * 100.0)
        raw = 0.6 * utilisation_score + 0.4 * growth_component
        origins.append(growth.origin)
    else:
        raw = utilisation_score

    score = clamp_score(max(0.0, min(100.0, raw)))
    origin = fold_origins(
        *origins,
        method="capacity_pressure",
        proxy=True,
        assumption="Capacity pressure estimated from passenger-per-operation ratio and growth trend",
    )
    return Present[float](value=score, origin=origin)
