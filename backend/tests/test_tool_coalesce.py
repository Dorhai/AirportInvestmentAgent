from app.agent.llm import ToolCall
from app.agent.conversation_frame import ConversationFrame
from app.agent.guardrails import Ambiguous, Resolved
from app.agent.tool_coalesce import coalesce_tools

def test_coalesces_metrics_to_compare() -> None:
    calls = [
        ToolCall(name="get_airport_metrics", arguments={"code": "BOS"}),
        ToolCall(name="get_airport_metrics", arguments={"code": "LAX"}),
        ToolCall(name="get_airport_metrics", arguments={"code": "SFO"}),
    ]
    frame = ConversationFrame(airports=["BOS", "LAX", "SFO"])
    mentions = Ambiguous(raw="", candidates=[])
    
    coalesced = coalesce_tools(calls, frame, mentions)
    
    assert len(coalesced) == 1
    assert coalesced[0].name == "compare_airports"
    assert set(coalesced[0].arguments["codes"]) == {"BOS", "LAX", "SFO"}

def test_trims_to_frame_when_superset_and_unmentioned() -> None:
    calls = [
        ToolCall(name="compare_airports", arguments={"codes": ["BOS", "LAX", "SFO", "JFK"]}),
    ]
    frame = ConversationFrame(airports=["BOS", "LAX"])
    mentions = Ambiguous(raw="", candidates=[])
    
    coalesced = coalesce_tools(calls, frame, mentions)
    
    assert len(coalesced) == 1
    assert coalesced[0].name == "compare_airports"
    assert set(coalesced[0].arguments["codes"]) == {"BOS", "LAX"}

def test_does_not_trim_when_user_mentioned_new_codes() -> None:
    calls = [
        ToolCall(name="compare_airports", arguments={"codes": ["BOS", "LAX", "SFO"]}),
    ]
    frame = ConversationFrame(airports=["BOS", "LAX"])
    mentions = Resolved(codes=["SFO"])
    
    coalesced = coalesce_tools(calls, frame, mentions)
    
    assert len(coalesced) == 1
    assert set(coalesced[0].arguments["codes"]) == {"BOS", "LAX", "SFO"}
