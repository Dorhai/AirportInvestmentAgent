from __future__ import annotations

import logging

from app.agent.conversation_frame import ConversationFrame
from app.agent.guardrails import Resolved, Ambiguous
from app.agent.llm import ToolCall

logger = logging.getLogger(__name__)

def coalesce_tools(
    calls: list[ToolCall], 
    frame: ConversationFrame,
    mentions: Resolved | Ambiguous,
) -> list[ToolCall]:
    """Coalesce multiple metrics/score calls into compare, and trim out-of-scope codes."""
    if not calls:
        return calls

    out: list[ToolCall] = []
    
    metrics_codes = set()
    score_codes = set()
    
    for call in calls:
        if call.name == "get_airport_metrics" and "code" in call.arguments:
            metrics_codes.add(call.arguments["code"])
        elif call.name == "get_airport_score" and "code" in call.arguments:
            score_codes.add(call.arguments["code"])
        else:
            out.append(call)
            
    # Coalesce multiple metrics into compare
    if len(metrics_codes) > 1:
        out.append(ToolCall(name="compare_airports", arguments={"codes": list(metrics_codes)}))
    elif len(metrics_codes) == 1:
        out.append(ToolCall(name="get_airport_metrics", arguments={"code": list(metrics_codes)[0]}))
        
    if len(score_codes) > 1:
        out.append(ToolCall(name="compare_airports", arguments={"codes": list(score_codes)}))
    elif len(score_codes) == 1:
        out.append(ToolCall(name="get_airport_score", arguments={"code": list(score_codes)[0]}))

    # Trim to frame if they generated too many compare/rank arguments and user didn't mention them explicitly
    # Wait, the prompt said: 
    # "If codes are a superset of frame.airports and the user message did not resolve new IATA codes via resolve_mentions, trim to frame.airports"
    
    if frame.airports and (isinstance(mentions, Ambiguous) or not mentions.codes):
        for i, call in enumerate(out):
            if call.name in ("compare_airports", "rank_airports"):
                codes = call.arguments.get("codes", [])
                if codes and set(codes).issuperset(set(frame.airports)) and len(codes) > len(frame.airports):
                    logger.info("Trimming coalesced tool %s codes %s to frame %s", call.name, codes, frame.airports)
                    out[i] = ToolCall(name=call.name, arguments={"codes": frame.airports})

    # Dedup identical calls
    seen = []
    final_out = []
    for call in out:
        k = (call.name, str(call.arguments))
        if k not in seen:
            seen.append(k)
            final_out.append(call)

    return final_out