"""Align structured chat evidence with multi-airport questions."""

from __future__ import annotations

import re

from app.agent.airport_scope import AirportScope
from app.agent.conversation_frame import ConversationFrame
from app.agent.guardrails import Resolved, resolve_mentions
from app.agent.llm import ToolCall
from app.agent.tools import execute
from app.models.chat import ToolResult
from app.services.analysis_service import Universe


def comparison_airport_codes(scope: AirportScope) -> list[str]:
    """Prefer airports named in the current message over stale session frame."""
    return [c.upper() for c in scope.codes[:4]]

_CAUSE_RE = re.compile(
    r"\b(cause|causes|driver|drivers|factor|factors|why)\b", re.IGNORECASE
)
_MULTI_SCOPE_RE = re.compile(
    r"\b(these|those|airports|expansion|candidate|candidates|compare|versus|vs\.?)\b",
    re.IGNORECASE,
)


_RANK_FOCUS_RE = re.compile(
    r"\b(highest|lowest|growth|capacity|terminal|gates|rank|ranked|top|most|benefit|close to)\b",
    re.IGNORECASE,
)


def message_wants_airport_comparison(message: str, scope: AirportScope) -> bool:
    lower = message.lower()
    if scope.source == "message" and len(scope.codes) >= 2:
        if re.search(r"\b(compare|versus|vs\.?)\b", lower):
            return True
    if len(scope.codes) < 2:
        return False
    if re.search(r"\b(compare|versus|vs\.?)\b", lower):
        return True
    if _RANK_FOCUS_RE.search(message) and not _CAUSE_RE.search(message):
        return False
    if _CAUSE_RE.search(message) and _MULTI_SCOPE_RE.search(message):
        # If we are following up on a ranking, don't force a compare table
        if scope.source == "ranking":
            return False
        return True
    return False


def upgrade_evidence_for_ui(
    message: str,
    scope: AirportScope,
    evidence: list[ToolResult],
    universe: Universe,
) -> list[ToolResult]:
    """Replace lone score cards with compare when the question spans frame airports."""
    if not evidence or not message_wants_airport_comparison(message, scope):
        return evidence

    if any(ev.kind == "comparison" for ev in evidence):
        return evidence

    if any(ev.kind == "ranking" for ev in evidence):
        frame_codes = comparison_airport_codes(scope)
        call = ToolCall(name="compare_airports", arguments={"codes": frame_codes})
        result = execute(call, universe)
        if result.kind != "rejection":
            return [result]
        return evidence

    codes_in_evidence: set[str] = set()
    for ev in evidence:
        codes_in_evidence.update(a.upper() for a in ev.airports)

    frame_codes = comparison_airport_codes(scope)
    if len(codes_in_evidence) >= 2 and codes_in_evidence.issuperset(set(frame_codes[:2])):
        return evidence

    call = ToolCall(name="compare_airports", arguments={"codes": frame_codes})
    result = execute(call, universe)
    if result.kind == "rejection":
        return evidence
    return [result]
