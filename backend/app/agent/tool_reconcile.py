"""Adjust LLM tool choices to match question intent (compare vs explain)."""

from __future__ import annotations

import re

from app.agent.guardrails import resolve_mentions
from app.agent.llm import ToolCall

_CAUSE_RE = re.compile(
    r"\b(cause|causes|driver|drivers|factor|factors|why)\b", re.IGNORECASE
)
_COMPARE_RE = re.compile(r"\b(compare|versus|vs\.?)\b", re.IGNORECASE)


def _airport_codes(message: str, calls: list[ToolCall]) -> list[str]:
    m = resolve_mentions(message)
    codes = list(m.codes) if hasattr(m, "codes") else []
    if len(codes) >= 2:
        return codes[:4]
    for call in calls:
        if call.name in ("explain_congestion", "compare_airports"):
            raw = call.arguments.get("codes") or []
            if len(raw) >= 2:
                return list(raw)[:4]
    return codes


def reconcile_tool_calls(message: str, calls: list[ToolCall]) -> list[ToolCall]:
    """Use compare_airports for side-by-side congestion questions, not explain alone."""
    if not calls:
        return calls

    lower = message.lower()
    if not _COMPARE_RE.search(lower):
        return calls

    codes = _airport_codes(message, calls)
    if len(codes) < 2:
        return calls

    names = {c.name for c in calls}
    wants_causes = bool(_CAUSE_RE.search(lower))

    if wants_causes:
        if "compare_airports" not in names and "explain_congestion" in names:
            return [
                ToolCall(name="compare_airports", arguments={"codes": codes}),
                *calls,
            ]
        return calls

    if names == {"explain_congestion"} or (
        "explain_congestion" in names and "compare_airports" not in names
    ):
        return [ToolCall(name="compare_airports", arguments={"codes": codes})]

    if "explain_congestion" in names and "compare_airports" in names:
        return [c for c in calls if c.name != "explain_congestion"]

    return calls
