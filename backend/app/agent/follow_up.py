from __future__ import annotations

import re

from app.agent.airport_scope import AirportScope, resolve_airport_scope
from app.agent.conversation_frame import ConversationFrame
from app.agent.intent_routing import plan_initial_tools, resolve_region
from app.agent.llm import ToolCall
from app.agent.session import Session
from app.models.chat import ToolResult


def _already_covered(
    kind: str,
    codes: list[str],
    region: str | None,
    carried: list[ToolResult] | None,
    *,
    metric: str | None = None,
) -> bool:
    codes_set = {c.upper() for c in codes}
    for ev in carried or []:
        if ev.kind != kind:
            continue
        if kind == "ranking":
            ev_region = getattr(ev, "region", None)
            ev_metric = getattr(ev, "metric", "opportunity_score")
            if metric and ev_metric != metric:
                continue
            if region and ev_region == region:
                return True
            if not region and ev_region in ("peer_universe", ""):
                return True
        elif codes_set and codes_set.issubset({a.upper() for a in ev.airports}):
            return True
    return False


def _compare_calls(
    airports: list[str], carried: list[ToolResult] | None
) -> list[ToolCall]:
    codes = airports[:4]
    if _already_covered("comparison", codes, None, carried):
        return []
    return [ToolCall(name="compare_airports", arguments={"codes": codes})]


def _explain_congestion_calls(
    airports: list[str], carried: list[ToolResult] | None
) -> list[ToolCall]:
    codes = airports[:4]
    if _already_covered("congestion_explain", codes, None, carried):
        return []
    return [ToolCall(name="explain_congestion", arguments={"codes": codes})]


def plan_fallback_tools(
    message: str,
    session: Session,
    frame: ConversationFrame,
    carried_evidence: list[ToolResult] | None = None,
) -> list[ToolCall]:
    """If the LLM chose no tools, pick deterministic tools from frame and keywords."""

    carried = carried_evidence
    lower = message.lower()
    
    if not frame.airports:
        return plan_initial_tools(message)

    scope = resolve_airport_scope(message, session, frame)

    if re.search(
        r"\b(cause|causes|driver|drivers|factor|factors|why|main\s+reason)\b", lower
    ):
        scoped = list(scope.codes)
        if len(scoped) >= 2 and re.search(r"\b(congestion|delay)\b", lower):
            if _already_covered("comparison", scoped, None, carried):
                return []
            return _explain_congestion_calls(scoped, carried)
        if len(frame.airports) == 1 and re.search(r"\b(unmet|demand)\b", lower):
            code = frame.airports[0]
            if _already_covered("unmet_explain", [code], None, carried):
                return []
            if _already_covered("unmet_demand", [code], None, carried):
                return []
            return [ToolCall(name="explain_unmet_demand", arguments={"code": code})]
        if re.search(r"\b(expansion|candidate|score|opportunity)\b", lower):
            scoped = list(scope.codes)
            if len(scoped) >= 2 and re.search(
                r"\b(factor|factors|why|driver|drivers)\b", lower
            ):
                return _compare_calls(scoped, carried)
            if scope.region:
                return [
                    ToolCall(name="rank_region", arguments={"region": scope.region})
                ]
            code = scoped[0] if scoped else frame.airports[0]
            if not _already_covered("score", [code], None, carried):
                return [ToolCall(name="get_airport_score", arguments={"code": code})]

    if re.search(
        r"\b(terminal|gates|gate|infrastructure|constraints|capacity pressure)\b",
        lower,
    ):
        region = frame.region or resolve_region(message)
        if region == "new_england":
            calls: list[ToolCall] = []
            if not _already_covered(
                "ranking", [], "new_england", carried, metric="capacity_pressure_score"
            ):
                calls.append(
                    ToolCall(
                        name="rank_by_metric",
                        arguments={
                            "metric": "capacity_pressure_score",
                            "region": "new_england",
                        },
                    )
                )
            if len(frame.airports) >= 1 and not _already_covered(
                "capacity_explain", frame.airports[:4], None, carried
            ):
                calls.append(
                    ToolCall(
                        name="explain_capacity_pressure",
                        arguments={"codes": frame.airports[:4]},
                    )
                )
            if calls:
                return calls
        if len(frame.airports) >= 1:
            return [
                ToolCall(
                    name="explain_capacity_pressure",
                    arguments={"codes": frame.airports[:4]},
                )
            ]

    if re.search(r"\b(passenger growth|highest growth|growth)\b", lower):
        region = frame.region or resolve_region(message) or ""
        metric = "passenger_growth"
        if not _already_covered("ranking", [], region or "peer_universe", carried, metric=metric):
            return [
                ToolCall(
                    name="rank_by_metric",
                    arguments={"metric": metric, "region": region},
                )
            ]

    if re.search(r"\b(benefit.*gates|terminal space|additional gates)\b", lower):
        region = frame.region or ""
        return [
            ToolCall(
                name="rank_by_metric",
                arguments={"metric": "capacity_pressure_score", "region": region},
            )
        ]

    scoped = list(scope.codes)
    if len(scoped) >= 2 and re.search(
        r"\b(congestion|compare|delay|capacity|cause|higher|lower|changed)\b", lower
    ):
        if re.search(r"\b(cause|driver|factor)\b", lower):
            return _explain_congestion_calls(scoped, carried)
        return _compare_calls(scoped, carried)

    if len(frame.airports) == 1 and re.search(r"\b(unmet|demand)\b", lower):
        code = frame.airports[0]
        if re.search(r"\bwhy\b", lower):
            if _already_covered("unmet_explain", [code], None, carried):
                return []
            return [ToolCall(name="explain_unmet_demand", arguments={"code": code})]
        if _already_covered("unmet_demand", [code], None, carried):
            return []
        return [
            ToolCall(name="get_unmet_demand", arguments={"code": code}),
            ToolCall(name="get_airport_score", arguments={"code": code}),
        ]

    if re.search(
        r"\b(long-haul|long haul|destinations|airlines|season|cargo)\b", lower
    ):
        scoped = list(scope.codes)
        if len(scoped) == 1:
            code = scoped[0]
            if _already_covered("long_haul", [code], None, carried):
                return []
            return [ToolCall(name="get_long_haul_percentage", arguments={"code": code})]
        if len(frame.airports) == 1:
            code = frame.airports[0]
            if _already_covered("long_haul", [code], None, carried):
                return []
            return [ToolCall(name="get_long_haul_percentage", arguments={"code": code})]

    if frame.region and re.search(
        r"\b(expansion|ranking|top|candidate|best|strong)\b", lower
    ):
        return [ToolCall(name="rank_region", arguments={"region": frame.region})]

    if re.search(r"\b(5[- ]?10\s*years?|simulate|future|trend)\b", lower):
        if len(frame.airports) == 1:
            return [
                ToolCall(
                    name="simulate_airport_growth",
                    arguments={"code": frame.airports[0], "growth_pct": 5.0},
                )
            ]
        return _compare_calls(list(scope.codes), carried)

    scoped = list(scope.codes)
    if len(scoped) >= 2:
        return _compare_calls(scoped, carried)

    return []
