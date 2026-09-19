from __future__ import annotations

from app.agent.prose_from_evidence import format_ranking_lead, merge_lead_with_prose
from app.models.chat import RankingResult
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


def test_format_ranking_lead_uses_same_values_as_ui() -> None:
    ev = RankingResult(
        airports=["BOS", "PVD"],
        snapshot_at="2025-04-01T00:00:00Z",
        ranked=[_score("BOS", 47.0), _score("PVD", 42.0)],
        region="new_england",
        peer_note="2 airports",
    )
    lead = format_ranking_lead(ev)
    assert "47.0" in lead
    assert "42.0" in lead
    assert "BOS" in lead


def test_merge_lead_with_prose() -> None:
    out = merge_lead_with_prose("Line 1", "Analysis here.")
    assert out.startswith("Line 1\n\nAnalysis")
