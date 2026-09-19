from __future__ import annotations


def normalize_min_max(value: float, lo: float, hi: float) -> float:
    """Scale *value* into 0–100 relative to [lo, hi].  Returns 50 when lo == hi."""
    if lo == hi:
        return 50.0
    raw = (value - lo) / (hi - lo) * 100.0
    return max(0.0, min(100.0, raw))


def normalize_percentage(value: float) -> float:
    """Clamp an already-percentage value to [0, 100]."""
    return max(0.0, min(100.0, value))


def clamp_score(value: float) -> float:
    """Clamp to [0, 100] and round to 1 decimal place."""
    return round(max(0.0, min(100.0, value)), 1)
