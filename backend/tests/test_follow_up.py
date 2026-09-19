from __future__ import annotations

import pytest

from app.agent.conversation_frame import ConversationFrame
from app.agent.follow_up import plan_fallback_tools
from app.agent.guardrails import build_follow_up_hints, resolve_mentions
from app.agent.llm import ToolCall
from app.agent.session import Session
from app.models.chat import ComparisonResult, UnmetDemandResult
from app.models.metrics import Live, Present


def test_build_follow_up_hints() -> None:
    frame = ConversationFrame(airports=["LAX", "SNA"])
    mentions = resolve_mentions("what causes congestion at each airport?")
    hints = build_follow_up_hints("what causes congestion at each airport?", frame, mentions, None)
    assert len(hints) == 1
    assert "LAX" in hints[0]
    assert "SNA" in hints[0]
    assert "unless the user names new airports or a new region" in hints[0]

def test_build_follow_up_hints_with_new_codes() -> None:
    frame = ConversationFrame(airports=["LAX", "SNA"])
    mentions = resolve_mentions("what about BOS?")
    hints = build_follow_up_hints("what about BOS?", frame, mentions, None)
    assert len(hints) == 0

def test_plan_fallback_compare_ignores_stale_frame_airports() -> None:
    frame = ConversationFrame(
        airports=["BOS", "PVD", "PWM", "BDL", "LAX", "SNA"],
        region="new_england",
    )
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "Compare LA and Santa Ana airport congestion levels.", session, frame
    )
    assert len(calls) == 1
    assert calls[0].name == "compare_airports"
    assert calls[0].arguments["codes"] == ["LAX", "SNA"]


def test_plan_fallback_tools_compare() -> None:
    frame = ConversationFrame(airports=["LAX", "SNA"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools("what causes congestion at each?", session, frame)
    assert len(calls) == 1
    assert calls[0].name == "explain_congestion"
    assert calls[0].arguments["codes"] == ["LAX", "SNA"]

def test_plan_fallback_tools_unmet() -> None:
    frame = ConversationFrame(airports=["SFO"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools("why is unmet demand so high?", session, frame)
    assert len(calls) == 1
    assert calls[0].name == "explain_unmet_demand"
    assert calls[0].arguments["code"] == "SFO"

def test_plan_fallback_tools_long_haul() -> None:
    frame = ConversationFrame(airports=["ANC"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools("what are the long-haul destinations?", session, frame)
    assert len(calls) == 1
    assert calls[0].name == "get_long_haul_percentage"
    assert calls[0].arguments["code"] == "ANC"


def test_plan_fallback_long_haul_uses_message_scope_after_ranking_turn() -> None:
    frame = ConversationFrame(
        airports=["PVD", "PWM", "BOS", "BDL", "SFO", "ANC", "JFK", "SNA", "LAX"],
        region=None,
    )
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "Which long-haul destinations are served directly from Boston?",
        session,
        frame,
    )
    assert len(calls) == 1
    assert calls[0].name == "get_long_haul_percentage"
    assert calls[0].arguments["code"] == "BOS"


def test_plan_fallback_tools_ranking() -> None:
    frame = ConversationFrame(airports=["BOS", "PVD"], region="new_england")
    session = Session(conversation_id="test")
    calls = plan_fallback_tools("which is best for expansion?", session, frame)
    assert len(calls) == 1
    assert calls[0].name == "rank_region"
    assert calls[0].arguments["region"] == "new_england"

def test_plan_fallback_tools_simulation() -> None:
    frame = ConversationFrame(airports=["BOS"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools("how about 5-10 years from now?", session, frame)
    assert len(calls) == 1
    assert calls[0].name == "simulate_airport_growth"
    assert calls[0].arguments["code"] == "BOS"
    assert calls[0].arguments["growth_pct"] == 5.0


def test_plan_fallback_skips_compare_when_carried() -> None:
    frame = ConversationFrame(airports=["LAX", "SNA"])
    session = Session(conversation_id="test")
    carried = [
        ComparisonResult(
            airports=["LAX", "SNA"],
            snapshot_at="2024-01-01T00:00:00Z",
            rows=[],
            highest_congestion="LAX",
            highest_opportunity_score="SNA",
            period_warning=None,
        )
    ]
    calls = plan_fallback_tools(
        "what causes congestion at each?", session, frame, carried_evidence=carried
    )
    assert calls == []


def test_plan_fallback_skips_unmet_when_carried() -> None:
    frame = ConversationFrame(airports=["SFO"])
    session = Session(conversation_id="test")
    carried = [
        UnmetDemandResult(
            airports=["SFO"],
            snapshot_at="2024-01-01T00:00:00Z",
            unmet_demand_index=Present(
                value=45.0,
                origin=Live(
                    source="test",
                    period="2024",
                    fetched_at="2024-01-01T00:00:00Z",
                ),
            ),
        )
    ]
    calls = plan_fallback_tools(
        "why is unmet demand so high?", session, frame, carried_evidence=carried
    )
    assert calls == []
