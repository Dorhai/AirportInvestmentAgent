from __future__ import annotations

from app.models.metrics import (
    Absent,
    DatumFloat,
    Present,
    fold_origins,
)
from app.models.score import PeerStats
from app.scoring.normalization import clamp_score, normalize_min_max

_METHODOLOGY = (
    "Unmet demand is estimated using demand growth "
    "weighted by capacity and delay pressure"
)


def calculate_unmet_demand_index(
    growth: DatumFloat,
    delay: DatumFloat,
    congestion: DatumFloat,
    peers: PeerStats,
) -> DatumFloat:
    """Proxy unmet-demand index (0–100).

    Weights: growth 50 %, delay 25 %, congestion 25 %.
    Absent inputs are dropped and the remaining weights renormalised.
    """
    components: list[tuple[float, float, Present[float]]] = []
    attempted: list[str] = []

    if isinstance(growth, Present):
        lo, hi = peers.bounds.get("demand_growth", (0.0, 1.0))
        components.append((0.50, normalize_min_max(growth.value, lo, hi), growth))
    elif isinstance(growth, Absent):
        attempted.extend(growth.attempted)

    if isinstance(delay, Present):
        components.append((0.25, delay.value, delay))
    elif isinstance(delay, Absent):
        attempted.extend(delay.attempted)

    if isinstance(congestion, Present):
        components.append((0.25, congestion.value, congestion))
    elif isinstance(congestion, Absent):
        attempted.extend(congestion.attempted)

    if not components:
        return Absent(
            reason="NOT_PUBLISHED",
            detail="all unmet-demand inputs absent",
            attempted=tuple(dict.fromkeys(attempted)),
        )

    total_w = sum(w for w, _, _ in components)
    raw = sum(w / total_w * s for w, s, _ in components)
    score = clamp_score(raw)

    origin = fold_origins(
        *(p.origin for _, _, p in components),
        method="unmet_demand_index",
        proxy=True,
        assumption=_METHODOLOGY,
    )
    return Present[float](value=score, origin=origin)
