"""Benchmark question → deterministic tool routing (no LLM)."""

from __future__ import annotations

import pytest

from app.agent.conversation_frame import ConversationFrame
from app.agent.follow_up import plan_fallback_tools
from app.agent.session import Session


def _tool_names(calls: list) -> list[str]:
    return [c.name for c in calls]


@pytest.mark.parametrize(
    "message,expected",
    [
        (
            "Which airports in New England are strong candidates for terminal expansion?",
            ["rank_region"],
        ),
        (
            "Compare LA and Santa Ana airport congestion levels.",
            ["compare_airports"],
        ),
        (
            "What is the percentage of long haul flights out of Anchorage airport?",
            ["get_long_haul_percentage"],
        ),
        (
            "What is the unmet flight demand in SFO airport and why?",
            ["get_unmet_demand", "get_airport_score"],
        ),
        (
            "Which airport has the largest gap between passenger demand and available capacity?",
            ["rank_by_metric"],
        ),
        (
            "Which airports are expected to experience the highest passenger growth?",
            ["rank_by_metric"],
        ),
        (
            "Which airports are likely to face capacity problems within the next 5–10 years?",
            ["rank_by_metric"],
        ),
    ],
)
def test_initial_turn_routing(message: str, expected: list[str]) -> None:
    frame = ConversationFrame(airports=[])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(message, session, frame)
    assert _tool_names(calls) == expected


def test_new_england_follow_up_factors() -> None:
    frame = ConversationFrame(airports=["BOS", "BDL", "PVD", "PWM"], region="new_england")
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "What factors make these airports good expansion candidates?", session, frame
    )
    assert calls and calls[0].name == "compare_airports"


def test_new_england_growth_rank() -> None:
    frame = ConversationFrame(airports=["BOS", "BDL", "PVD", "PWM"], region="new_england")
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "Which airports are expected to experience the highest passenger growth?", session, frame
    )
    assert calls[0].name == "rank_by_metric"
    assert calls[0].arguments["metric"] == "passenger_growth"


def test_new_england_capacity_terminal() -> None:
    frame = ConversationFrame(airports=["BOS", "BDL", "PVD", "PWM"], region="new_england")
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "Which airports are already operating close to terminal capacity?", session, frame
    )
    assert "rank_by_metric" in _tool_names(calls) or "explain_capacity_pressure" in _tool_names(
        calls
    )


def test_lax_sna_congestion_causes() -> None:
    frame = ConversationFrame(airports=["LAX", "SNA"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "What are the main causes of congestion at each airport?", session, frame
    )
    assert _tool_names(calls) == ["explain_congestion"]


def test_lax_sna_delay_congestion_compare() -> None:
    frame = ConversationFrame(airports=["LAX", "SNA"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools(
        "Which airport experiences more delays caused by congestion?", session, frame
    )
    assert _tool_names(calls) == ["compare_airports"]


def test_sfo_unmet_why_follow_up() -> None:
    frame = ConversationFrame(airports=["SFO"])
    session = Session(conversation_id="test")
    calls = plan_fallback_tools("why is unmet demand so high?", session, frame)
    assert _tool_names(calls) == ["explain_unmet_demand"]


def test_declined_questions_return_no_tools() -> None:
    frame = ConversationFrame(airports=[])
    session = Session(conversation_id="test")
    for q in (
        "Which airports are losing passengers to nearby competing airports?",
        "Where could adding one additional daily route generate the most value?",
        "During which hours or days is congestion highest?",
        "Which routes have the highest unmet demand?",
    ):
        assert plan_fallback_tools(q, session, frame) == [], q
