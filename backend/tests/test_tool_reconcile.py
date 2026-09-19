from app.agent.llm import ToolCall
from app.agent.tool_reconcile import reconcile_tool_calls


def test_compare_question_replaces_explain_only() -> None:
    msg = "Compare LA and Santa Ana airport congestion levels."
    calls = [
        ToolCall(
            name="explain_congestion",
            arguments={"codes": ["LAX", "SNA"]},
        )
    ]
    out = reconcile_tool_calls(msg, calls)
    assert len(out) == 1
    assert out[0].name == "compare_airports"
    assert out[0].arguments["codes"] == ["LAX", "SNA"]
