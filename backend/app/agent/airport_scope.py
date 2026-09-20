from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.agent.conversation_frame import ConversationFrame
from app.agent.guardrails import Resolved, resolve_mentions
from app.agent.intent_routing import resolve_region
from app.agent.session import Session
from app.models.chat import RankingResult


@dataclass(frozen=True)
class AirportScope:
    codes: tuple[str, ...]
    region: str | None
    source: Literal["message", "referent", "last_turn", "ranking"]


def _last_turn_airport_codes(session: Session) -> list[str]:
    last_ev = session.last_evidence
    codes: list[str] = []
    for ev in last_ev:
        for code in ev.airports:
            if code not in codes:
                codes.append(code)
    return codes


def _referent_scope(
    message: str, last_codes: list[str], ranked: list[str] | None, frame_airports: list[str]
) -> list[str] | None:
    from app.agent.guardrails import _REFERENT_PATTERNS, _PLURAL_REFERENT_PATTERNS, _ORDINAL_MAP

    lower = message.lower()
    for pattern in _REFERENT_PATTERNS:
        m = pattern.search(lower)
        if m:
            matched = m.group(0).lower()
            for word, idx in _ORDINAL_MAP.items():
                if word in matched:
                    # Prefer ranked order if available, else last codes, else frame
                    source_list = ranked if ranked else (last_codes if last_codes else frame_airports)
                    try:
                        return [source_list[idx]]
                    except IndexError:
                        return None
            return ranked if ranked else (last_codes if last_codes else frame_airports)

    for pattern in _PLURAL_REFERENT_PATTERNS:
        if pattern.search(lower):
            return ranked if ranked else (last_codes if last_codes else frame_airports)

    return None


def resolve_airport_scope(
    message: str,
    session: Session,
    frame: ConversationFrame,
) -> AirportScope:
    """Determine the precise airport scope for the current turn."""
    
    # 1. Explicit mentions in message
    mentions = resolve_mentions(message)
    if isinstance(mentions, Resolved) and len(mentions.codes) >= 2:
        return AirportScope(
            codes=tuple(mentions.codes),
            region=resolve_region(message) or frame.region,
            source="message",
        )

    last_codes = _last_turn_airport_codes(session)
    
    # 2. Referents (singular or plural)
    ref_codes = _referent_scope(message, last_codes, frame.ranked_airports, frame.airports)
    if ref_codes is not None:
        return AirportScope(
            codes=tuple(ref_codes),
            region=resolve_region(message) or frame.region,
            source="referent",
        )

    # 3. Explicit single mention (if any)
    if isinstance(mentions, Resolved) and len(mentions.codes) == 1:
        return AirportScope(
            codes=tuple(mentions.codes),
            region=resolve_region(message) or frame.region,
            source="message",
        )

    # 4. Default active scope (last turn)
    if last_codes:
        # If last turn was a ranking, use ranked airports as scope
        source: Literal["last_turn", "ranking"] = "last_turn"
        codes = last_codes
        if session.last_evidence and isinstance(session.last_evidence[0], RankingResult):
            source = "ranking"
            codes = frame.ranked_airports or last_codes
            
        return AirportScope(
            codes=tuple(codes),
            region=resolve_region(message) or frame.region,
            source=source,
        )

    # 5. Fallback to frame union (if no last turn)
    return AirportScope(
        codes=tuple(frame.airports),
        region=resolve_region(message) or frame.region,
        source="last_turn",
    )
