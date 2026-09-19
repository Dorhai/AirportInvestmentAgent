"""Pick which tool results to show in UI and ground LLM numbers."""

from __future__ import annotations

import re

from app.agent.airport_scope import AirportScope
from app.agent.conversation_frame import ConversationFrame
from app.agent.guardrails import Resolved, resolve_mentions
from app.models.chat import ToolResult


def _carried_matches_scope(ev: ToolResult, scope: AirportScope) -> bool:
    ev_set = {a.upper() for a in ev.airports}
    scope_set = {c.upper() for c in scope.codes}
    if not scope_set:
        return False
    if len(scope_set) >= 2:
        return scope_set.issubset(ev_set) or ev_set == scope_set
    return bool(scope_set & ev_set)


_ROUTE_DETAIL_RE = re.compile(
    r"\b(long[- ]haul|destinations?|routes?|airlines?|non[- ]stop|direct\s+flights?|served\s+from)\b",
    re.IGNORECASE,
)


def should_refresh_region_ranking(message: str, scope: AirportScope) -> bool:
    if not scope.region:
        return False
    lower = message.lower()
    return bool(
        re.search(
            r"\b(expansion|candidate|candidates|ranking|rank|top|strong|best)\b",
            lower,
        )
    )


def carried_evidence_for_turn(
    message: str,
    scope: AirportScope,
    carried: list[ToolResult],
) -> list[ToolResult]:
    """When no new tools run, reuse the most relevant prior analytical result."""
    if not carried:
        return []

    lower = message.lower()

    if _ROUTE_DETAIL_RE.search(message):
        return []

    if re.search(
        r"\b(cause|causes|driver|drivers|why|explain|constraint|constraints|tell me more)\b",
        lower,
    ):
        return []

    if not re.search(
        r"\b(which|what airports|list|rank|ranking|top|candidate|candidates|expansion|compare|show me)\b",
        lower,
    ):
        return []

    if scope.region and should_refresh_region_ranking(message, scope):
        for ev in reversed(carried):
            if ev.kind == "ranking" and getattr(ev, "region", None) == scope.region:
                metric = getattr(ev, "metric", "opportunity_score")
                if metric == "opportunity_score" and _carried_matches_scope(ev, scope):
                    return [ev]

    if re.search(r"\b(compare|versus|vs\.?|factor|factors)\b", lower):
        for ev in reversed(carried):
            if ev.kind == "comparison" and _carried_matches_scope(ev, scope):
                return [ev]

    if re.search(r"\b(passenger growth|growth|capacity|congestion)\b", lower):
        for ev in reversed(carried):
            if (
                ev.kind == "ranking"
                and getattr(ev, "metric", "opportunity_score") != "opportunity_score"
                and _carried_matches_scope(ev, scope)
            ):
                return [ev]

    for ev in reversed(carried):
        if ev.kind in ("ranking", "comparison", "score") and _carried_matches_scope(
            ev, scope
        ):
            return [ev]

    return []
