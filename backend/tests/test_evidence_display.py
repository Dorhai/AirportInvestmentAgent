from __future__ import annotations

from app.agent.conversation_frame import ConversationFrame
from app.agent.display_evidence import comparison_airport_codes
from app.agent.evidence_display import carried_evidence_for_turn
from app.agent.airport_scope import resolve_airport_scope
from app.agent.session import Exchange, Session
from app.models.chat import ComparisonResult, RankingResult
from app.models.metrics import Present, Sample
from app.models.score import AirportScore


def _score(code: str, opp: float) -> AirportScore:
    origin = Sample(source="t", period="CY2024", citation="")
    p = lambda v: Present[float](value=v, origin=origin)  # noqa: E731
    return AirportScore(
        airport_code=code,  # type: ignore[arg-type]
        airport_name=f"Airport {code}",
        opportunity_score=p(opp),
        demand_growth_score=p(50.0),
        congestion_score=p(50.0),
        delay_pressure_score=p(50.0),
        capacity_pressure_score=p(50.0),
        confidence="HIGH",
        snapshot_at="2025-04-01T00:00:00Z",
        assumptions=[],
        limitations=[],
        sources=[],
    )


def test_comparison_airport_codes_prefers_message_mentions() -> None:
    frame = ConversationFrame(
        airports=["BOS", "PVD", "PWM", "BDL", "LAX", "SNA"],
        region="new_england",
    )
    session = Session(conversation_id="test")
    msg = "Compare LA and Santa Ana airport congestion levels."
    scope = resolve_airport_scope(msg, session, frame)
    codes = comparison_airport_codes(scope)
    assert codes == ["LAX", "SNA"]


def test_carried_compare_skips_stale_region_when_message_names_other_airports() -> None:
    frame = ConversationFrame(airports=["BOS", "PVD", "PWM", "BDL"], region="new_england")
    session = Session(conversation_id="test")
    ne_compare = ComparisonResult(
        airports=["BOS", "PVD", "PWM", "BDL"],
        snapshot_at="2025-04-01T00:00:00Z",
        rows=[],
        highest_congestion=None,
        highest_opportunity_score=None,
        period_warning=None,
    )
    msg = "Compare LA and Santa Ana airport congestion levels."
    scope = resolve_airport_scope(msg, session, frame)
    carried = carried_evidence_for_turn(
        msg,
        scope,
        [ne_compare],
    )
    assert carried == []


def test_carried_skips_route_detail_follow_up_after_peer_ranking() -> None:
    frame = ConversationFrame(
        airports=["PVD", "PWM", "BOS", "BDL", "SFO", "ANC", "JFK", "SNA", "LAX"],
        region=None,
    )
    session = Session(conversation_id="test")
    ranking = RankingResult(
        airports=["PVD", "PWM", "BOS", "BDL", "SFO", "ANC", "JFK", "SNA", "LAX"],
        snapshot_at="2025-04-01T00:00:00Z",
        ranked=[_score("PVD", 100.0)],
        region="peer_universe",
        peer_note="9 airports",
        metric="passenger_growth",
    )
    session.exchanges.append(
        Exchange(
            user_message="Compare Miami and Fort Lauderdale airport traffic growth.",
            reply="...",
            evidence=[ranking],
        )
    )
    msg = "Which long-haul destinations are served directly from Boston?"
    scope = resolve_airport_scope(msg, session, frame)
    carried = carried_evidence_for_turn(msg, scope, session.accumulated_evidence())
    assert carried == []


def test_carried_ranking_skips_new_england_when_mentions_are_lax_sna() -> None:
    frame = ConversationFrame(airports=["BOS", "PVD"], region="new_england")
    session = Session(conversation_id="test")
    ranking = RankingResult(
        airports=["BOS", "PVD"],
        snapshot_at="2025-04-01T00:00:00Z",
        ranked=[_score("BOS", 47.0), _score("PVD", 42.0)],
        region="new_england",
        peer_note="2 airports",
        metric="passenger_growth",
    )
    msg = "Compare LA and Santa Ana airport congestion levels."
    scope = resolve_airport_scope(msg, session, frame)
    carried = carried_evidence_for_turn(
        msg,
        scope,
        [ranking],
    )
    assert carried == []
