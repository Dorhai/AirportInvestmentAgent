from __future__ import annotations

from app.agent.airport_scope import resolve_airport_scope
from app.agent.conversation_frame import ConversationFrame
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


def test_resolve_airport_scope_3_turn_regression() -> None:
    session = Session(conversation_id="test")
    
    # Turn 1: Compare LAX and SNA
    comp = ComparisonResult(
        airports=["LAX", "SNA"],
        snapshot_at="2025-04-01T00:00:00Z",
        rows=[],
        highest_congestion=None,
        highest_opportunity_score=None,
        period_warning=None,
    )
    session.exchanges.append(Exchange(user_message="Compare LAX and SNA", reply="...", evidence=[comp]))
    
    # Turn 2: NE ranking
    rank = RankingResult(
        airports=["BOS", "PVD", "PWM", "BDL"],
        snapshot_at="2025-04-01T00:00:00Z",
        ranked=[_score("BOS", 47.0), _score("PVD", 42.0), _score("PWM", 33.5), _score("BDL", 30.8)],
        region="new_england",
        peer_note="",
        metric="opportunity_score",
    )
    session.exchanges.append(Exchange(user_message="Rank NE", reply="...", evidence=[rank]))
    
    frame = ConversationFrame(
        airports=["LAX", "SNA", "BOS", "PVD", "PWM", "BDL"],
        region="new_england",
        ranked_airports=["BOS", "PVD", "PWM", "BDL"],
    )
    
    # Turn 3: "these airports factors"
    scope = resolve_airport_scope("What factors make these airports good candidates?", session, frame)
    
    assert scope.source == "referent"
    assert list(scope.codes) == ["BOS", "PVD", "PWM", "BDL"]


def test_resolve_airport_scope_explicit_mentions_override() -> None:
    session = Session(conversation_id="test")
    rank = RankingResult(
        airports=["BOS", "PVD", "PWM", "BDL"],
        snapshot_at="2025-04-01T00:00:00Z",
        ranked=[_score("BOS", 47.0), _score("PVD", 42.0), _score("PWM", 33.5), _score("BDL", 30.8)],
        region="new_england",
        peer_note="",
        metric="opportunity_score",
    )
    session.exchanges.append(Exchange(user_message="Rank NE", reply="...", evidence=[rank]))
    
    frame = ConversationFrame(
        airports=["BOS", "PVD", "PWM", "BDL"],
        region="new_england",
        ranked_airports=["BOS", "PVD", "PWM", "BDL"],
    )
    
    scope = resolve_airport_scope("Compare LAX and SNA", session, frame)
    assert scope.source == "message"
    assert set(scope.codes) == {"LAX", "SNA"}


def test_resolve_airport_scope_ordinal_on_ranking() -> None:
    session = Session(conversation_id="test")
    rank = RankingResult(
        airports=["BOS", "PVD", "PWM", "BDL"],
        snapshot_at="2025-04-01T00:00:00Z",
        ranked=[_score("BOS", 47.0), _score("PVD", 42.0), _score("PWM", 33.5), _score("BDL", 30.8)],
        region="new_england",
        peer_note="",
        metric="opportunity_score",
    )
    session.exchanges.append(Exchange(user_message="Rank NE", reply="...", evidence=[rank]))
    
    frame = ConversationFrame(
        airports=["BOS", "PVD", "PWM", "BDL"],
        region="new_england",
        ranked_airports=["BOS", "PVD", "PWM", "BDL"],
    )
    
    scope = resolve_airport_scope("Tell me about the first one", session, frame)
    assert scope.source == "referent"
    assert list(scope.codes) == ["BOS"]
