"""Deterministic first-turn tool selection when the LLM returns no tools."""

from __future__ import annotations

import re

from app.agent.guardrails import Resolved, resolve_mentions
from app.agent.llm import ToolCall
from app.models.airport import IATA, REGIONS, Region

_REGION_ALIASES: dict[str, Region] = {
    "new england": "new_england",
    "west coast": "west_coast",
    "northeast": "northeast",
    "southern california": "california",
    "la area": "california",
    "alaska": "alaska",
}


def resolve_region(text: str) -> Region | None:
    lower = text.lower()
    for phrase, slug in _REGION_ALIASES.items():
        if phrase in lower:
            return slug
    for slug in REGIONS:
        if slug.replace("_", " ") in lower:
            return slug
    return None


def _codes_from_message(message: str) -> list[IATA]:
    m = resolve_mentions(message)
    if isinstance(m, Resolved):
        return list(m.codes)  # type: ignore[arg-type]
    return []


def plan_initial_tools(message: str) -> list[ToolCall]:
    """Pick tools for analytical questions before conversation frame exists."""
    lower = message.lower()
    codes = _codes_from_message(message)
    region = resolve_region(message)

    if re.search(r"\b(long[- ]haul|flight distance|route distance)\b", lower) and (
        "ANC" in codes or "anchorage" in lower or len(codes) == 1
    ):
        target = codes[0] if len(codes) == 1 else "ANC"
        return [ToolCall(name="get_long_haul_percentage", arguments={"code": target})]

    if re.search(r"\bunmet\b", lower) and ("SFO" in codes or "san francisco" in lower):
        return [
            ToolCall(name="get_unmet_demand", arguments={"code": "SFO"}),
            ToolCall(name="get_airport_score", arguments={"code": "SFO"}),
        ]

    if region == "new_england" and re.search(
        r"\b(expansion|terminal|candidate|strong)\b", lower
    ):
        return [ToolCall(name="rank_region", arguments={"region": "new_england"})]

    if len(codes) >= 2 and re.search(r"\b(congestion|compare|delay)\b", lower):
        return [
            ToolCall(name="compare_airports", arguments={"codes": codes[:4]}),
        ]

    if ("LAX" in codes and "SNA" in codes) or (
        re.search(r"\b(los angeles|lax)\b", lower)
        and re.search(r"\b(santa ana|john wayne|sna)\b", lower)
        and re.search(r"\bcongestion\b", lower)
    ):
        return [
            ToolCall(
                name="compare_airports",
                arguments={"codes": ["LAX", "SNA"]},
            )
        ]

    if re.search(
        r"\b(gap|demand).*(capacity|terminal)|capacity.*(demand|gap)\b", lower
    ):
        return [
            ToolCall(
                name="rank_by_metric",
                arguments={"metric": "capacity_pressure_score", "region": ""},
            )
        ]

    if re.search(r"\b(losing passengers|competing airports|passenger leakage)\b", lower):
        return []

    if re.search(r"\b(value|roi).*(route|daily route)\b", lower):
        return []

    if re.search(r"\b(highest passenger growth|passenger growth)\b", lower):
        if region:
            return [
                ToolCall(
                    name="rank_by_metric",
                    arguments={"metric": "passenger_growth", "region": region},
                )
            ]
        return [
            ToolCall(
                name="rank_by_metric",
                arguments={"metric": "passenger_growth", "region": ""},
            )
        ]

    if re.search(r"\b(5\s*[-–]?\s*10\s*years?|capacity problems)\b", lower):
        if len(codes) == 1:
            return [
                ToolCall(
                    name="simulate_airport_growth",
                    arguments={"code": codes[0], "growth_pct": 5.0},
                )
            ]
        return [
            ToolCall(
                name="rank_by_metric",
                arguments={"metric": "capacity_pressure_score", "region": ""},
            )
        ]

    if region and re.search(r"\b(rank|expansion|candidate|best|top)\b", lower):
        return [ToolCall(name="rank_region", arguments={"region": region})]

    return []
