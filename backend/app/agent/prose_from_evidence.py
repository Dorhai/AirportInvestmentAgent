"""Deterministic prose snippets from tool results (scores must match UI)."""

from __future__ import annotations

import re
from app.models.chat import ComparisonResult, RankingResult, ToolResult
from app.models.metrics import Present

_CAUSE_RE = re.compile(
    r"\b(cause|causes|driver|drivers|factor|factors|why|explain|tell me more|detail)\b", re.IGNORECASE
)
_SIMULATION_RE = re.compile(
    r"\b(simulate|what if|if|growth|grow|increase|decrease)\b", re.IGNORECASE
)

def should_use_deterministic_prose(message: str, evidence: list[ToolResult]) -> bool:
    if len(evidence) != 1:
        return False
    ev = evidence[0]
    if not isinstance(ev, (RankingResult, ComparisonResult)):
        return False
    
    if _CAUSE_RE.search(message):
        return False
    if _SIMULATION_RE.search(message):
        return False
        
    return True


def _fmt_score(d: Present[float] | object) -> str:
    if isinstance(d, Present):
        return f"{d.value:.1f}"
    return "---"


def format_ranking_lead(ev: RankingResult) -> str:
    lines = [
        f"Opportunity scores ({ev.region.replace('_', ' ')}, snapshot {ev.snapshot_at[:10]}):"
    ]
    for i, s in enumerate(ev.ranked, start=1):
        name = s.airport_name or s.airport_code
        lines.append(
            f"{i}. {name} ({s.airport_code}): {_fmt_score(s.opportunity_score)} "
            f"[{s.confidence}]"
        )
    return "\n".join(lines)


def format_comparison_lead(ev: ComparisonResult) -> str:
    lines = [f"Airport comparison (snapshot {ev.snapshot_at[:10]}):"]
    for row in ev.rows:
        s = row.score
        name = s.airport_name or s.airport_code
        lines.append(
            f"• {name} ({s.airport_code}): opportunity {_fmt_score(s.opportunity_score)}"
        )
    return "\n".join(lines)


def lead_paragraph_for_evidence(evidence: list[ToolResult]) -> str | None:
    if len(evidence) != 1:
        return None
    ev = evidence[0]
    if isinstance(ev, RankingResult):
        return format_ranking_lead(ev)
    if isinstance(ev, ComparisonResult):
        return format_comparison_lead(ev)
    return None


def merge_lead_with_prose(lead: str, prose: str) -> str:
    prose = prose.strip()
    if not prose:
        return lead
    return f"{lead}\n\n{prose}"
