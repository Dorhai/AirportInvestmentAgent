from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.models.airport import IATA
from app.models.chat import RankingResult

if TYPE_CHECKING:
    from app.agent.session import Session
    from app.agent.airport_scope import AirportScope


@dataclass(frozen=True)
class ConversationFrame:
    airports: list[IATA]
    region: str | None = None
    last_evidence_kinds: list[str] = field(default_factory=list)
    ranked_airports: list[IATA] | None = None


def frame_from_session(session: "Session") -> ConversationFrame:
    """Derives a deterministic context frame from all evidence-bearing turns in the session."""
    codes: list[IATA] = []
    region: str | None = None
    ranked: list[IATA] | None = None
    last_kinds: list[str] = []

    ev_exchanges = [ex for ex in session.exchanges if ex.evidence]

    if ev_exchanges:
        last_ev = ev_exchanges[-1].evidence
        last_kinds = list(dict.fromkeys(ev.kind for ev in last_ev))

    for ex in reversed(ev_exchanges):
        for ev in ex.evidence:
            if isinstance(ev, RankingResult) and region is None:
                region = ev.region
                ranked = [s.airport_code for s in ev.ranked]

    # Collect airports from all evidence turns
    for ex in ev_exchanges:
        for ev in ex.evidence:
            for code in ev.airports:
                if code not in codes:
                    codes.append(code) # type: ignore

    return ConversationFrame(
        airports=codes,
        region=region,
        last_evidence_kinds=last_kinds,
        ranked_airports=ranked,
    )


def render_frame_digest(frame: ConversationFrame, scope: AirportScope) -> str:
    """Renders the frame into a short text block for the LLM."""
    if not frame.airports:
        return ""

    lines = []
    if scope.codes:
        lines.append(f"In scope this turn: {', '.join(scope.codes)}")
    
    other_airports = [c for c in frame.airports if c not in scope.codes]
    if other_airports:
        lines.append(f"Also discussed earlier: {', '.join(other_airports)}")

    if frame.region:
        lines.append(f"Active region: {frame.region}")
    if frame.last_evidence_kinds:
        lines.append(f"Last tools used: {', '.join(frame.last_evidence_kinds)}")
    if frame.ranked_airports:
        lines.append(f"Current ranking order: {', '.join(frame.ranked_airports)}")
    
    return "\n".join(lines)
