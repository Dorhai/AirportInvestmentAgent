from __future__ import annotations

from app.agent.conversation_frame import ConversationFrame
from app.agent.display_evidence import (
    comparison_airport_codes,
    message_wants_airport_comparison,
)
from app.agent.airport_scope import resolve_airport_scope
from app.agent.session import Session


def test_message_wants_comparison_for_factors_question() -> None:
    frame = ConversationFrame(airports=["BOS", "PVD"], region="new_england")
    session = Session(conversation_id="test")
    scope = resolve_airport_scope("What factors make these airports good expansion candidates?", session, frame)
    assert message_wants_airport_comparison(
        "What factors make these airports good expansion candidates?", scope
    )


def test_message_wants_comparison_false_for_single_airport_frame() -> None:
    frame = ConversationFrame(airports=["BOS"], region=None)
    session = Session(conversation_id="test")
    scope = resolve_airport_scope("What factors make this airport a good expansion candidate?", session, frame)
    assert not message_wants_airport_comparison(
        "What factors make this airport a good expansion candidate?", scope
    )


def test_message_wants_comparison_true_for_explicit_lax_sna() -> None:
    frame = ConversationFrame(airports=["BOS", "PVD", "PWM", "BDL"], region="new_england")
    session = Session(conversation_id="test")
    scope = resolve_airport_scope("Compare LA and Santa Ana airport congestion levels.", session, frame)
    assert message_wants_airport_comparison(
        "Compare LA and Santa Ana airport congestion levels.",
        scope,
    )


def test_message_wants_comparison_false_for_rank_focus() -> None:
    frame = ConversationFrame(airports=["BOS", "PVD"], region="new_england")
    session = Session(conversation_id="test")
    scope = resolve_airport_scope("Which airports are expected to experience the highest passenger growth?", session, frame)
    assert not message_wants_airport_comparison(
        "Which airports are expected to experience the highest passenger growth?",
        scope,
    )
