from __future__ import annotations

from app.models.metrics import (
    Absent,
    DatumFloat,
    DatumInt,
    Origin,
    Present,
    fold_origins,
)


def _sources_from_origin(origin: Origin) -> tuple[str, ...]:
    if hasattr(origin, "source"):
        return (origin.source,)
    if hasattr(origin, "sources"):
        return origin.sources
    return ()


def calculate_passenger_growth(
    current: DatumInt,
    previous: DatumInt,
) -> DatumFloat:
    """``(current - previous) / previous``, pure and deterministic.

    Returns ``Absent(NOT_PUBLISHED)`` when either input is absent.
    Returns ``Absent(OUT_OF_SCOPE)`` when *previous* ≤ 0.
    """
    if isinstance(current, Absent) or isinstance(previous, Absent):
        parts: list[str] = []
        if isinstance(current, Absent):
            parts.extend(current.attempted)
        if isinstance(previous, Absent):
            parts.extend(previous.attempted)
        return Absent(
            reason="NOT_PUBLISHED",
            detail="required passenger volume datum absent",
            attempted=tuple(dict.fromkeys(parts)),
        )

    if previous.value <= 0:
        attempted = list(
            dict.fromkeys(
                _sources_from_origin(current.origin)
                + _sources_from_origin(previous.origin)
            )
        )
        return Absent(
            reason="OUT_OF_SCOPE",
            detail="previous <= 0",
            attempted=tuple(attempted),
        )

    growth = (current.value - previous.value) / previous.value
    origin = fold_origins(
        current.origin, previous.origin, method="passenger_growth"
    )
    return Present[float](value=growth, origin=origin)
