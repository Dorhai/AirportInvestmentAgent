"""Capability decline hints for questions outside published data."""

from __future__ import annotations

import re

_DECLINE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(hour|hours|day of week|peak time|peak day)\b", re.I),
        "Hourly or daily congestion is not in the dataset. Compare congestion or delay pressure scores between airports instead.",
    ),
    (
        re.compile(r"\b(route|routes|airline|airlines|slot|slots)\b", re.I),
        "Route- and airline-level detail is not available. Use long-haul percentage, connectivity counts, or peer rankings instead.",
    ),
    (
        re.compile(r"\b(losing passengers|competing airports|leakage)\b", re.I),
        "Passenger diversion between airports is not modeled. Compare opportunity or unmet demand indices across peers instead.",
    ),
    (
        re.compile(
            r"\b(value|roi|revenue).*(route|daily route)\b", re.I
        ),
        "Financial value of a new route is out of scope. Rank airports by unmet demand or capacity pressure instead.",
    ),
]


def capability_hints(message: str) -> list[str]:
    out: list[str] = []
    for pattern, hint in _DECLINE_HINTS:
        if pattern.search(message):
            out.append(hint)
    return out
