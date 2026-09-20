"""Tests for agent tool execution and ChatResponse assembly."""

from __future__ import annotations

import pytest

from app.agent.llm import ToolCall
from app.agent.tools import (
    TOOLS,
    CodeArgs,
    CodesArgs,
    RegionArgs,
    SimArgs,
    execute,
)
from app.models.airport import Airport
from app.models.chat import (
    ChatResponse,
    ComparisonResult,
    LongHaulResult,
    MetricsResult,
    RankingResult,
    ScoreResult,
    SimulationResult,
    ToolRejection,
    UnmetDemandResult,
)
from app.models.metrics import (
    Absent,
    AirportDossier,
    AirportMetrics,
    DatumFloat,
    DatumInt,
    Live,
    Present,
    Sample,
)
from app.models.score import AirportScore, PeerStats
from app.scoring.expansion_score import score_dossier
from app.services.analysis_service import Universe


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def _live(source: str = "FAA", period: str = "2025-Q1") -> Live:
    return Live(source=source, period=period, fetched_at="2025-04-01T00:00:00Z")


def _sample(source: str = "BTS", period: str = "2024") -> Sample:
    return Sample(source=source, period=period, citation="BTS T-100 2024")


def _pi(v: int, origin: Live | Sample | None = None) -> Present[int]:
    return Present[int](value=v, origin=origin or _live())


def _pf(v: float, origin: Live | Sample | None = None) -> Present[float]:
    return Present[float](value=v, origin=origin or _live())


def _absent(reason: str = "NOT_PUBLISHED") -> Absent:
    return Absent(reason=reason, detail="test", attempted=("test_provider",))  # type: ignore[arg-type]


_PEERS = PeerStats(
    bounds={
        "annual_operations": (50_000.0, 500_000.0),
        "passenger_volume": (1_000_000.0, 50_000_000.0),
        "demand_growth": (0.0, 0.15),
        "pax_per_operation": (50.0, 200.0),
    },
    universe_codes=("BOS", "LAX"),
)

_SNAPSHOT = "2025-04-01T00:00:00Z"

_BOS = Airport(
    iata_code="BOS", icao_code="KBOS", name="Boston Logan",
    city="Boston", state="MA", latitude=42.3656, longitude=-71.0096,
)
_LAX = Airport(
    iata_code="LAX", icao_code="KLAX", name="Los Angeles",
    city="Los Angeles", state="CA", latitude=33.9425, longitude=-118.4081,
)


def _metrics(code: str = "BOS") -> AirportMetrics:
    return AirportMetrics(
        airport_code=code,  # type: ignore[arg-type]
        passenger_volume=_pi(20_000_000),
        previous_passenger_volume=_pi(18_000_000),
        annual_operations=_pi(200_000),
        delayed_flights_pct=_pf(22.0),
        average_delay_minutes=_pf(18.0),
        long_haul_flights=_pi(5000),
        total_departures=_pi(100_000),
    )


from app.models.context import AirportContext

def _dossier(airport: Airport, code: str = "BOS") -> AirportDossier:
    return AirportDossier(
        airport=airport,
        metrics=_metrics(code),
        passenger_growth=_pf(0.08),
        long_haul_pct=_pf(12.5),
        unmet_demand_index=_pf(55.0),
        context=AirportContext(),
        snapshot_at=_SNAPSHOT,
    )


def _universe() -> Universe:
    bos_d = _dossier(_BOS, "BOS")
    lax_d = _dossier(_LAX, "LAX")
    bos_s = score_dossier(bos_d, _PEERS)
    lax_s = score_dossier(lax_d, _PEERS)
    return Universe(
        snapshot_at=_SNAPSHOT,
        dossiers={"BOS": bos_d, "LAX": lax_d},
        scores={"BOS": bos_s, "LAX": lax_s},
        peers=_PEERS,
        failures=[],
    )


# ==================================================================
# Registry
# ==================================================================


class TestToolRegistry:
    def test_all_tools_registered(self) -> None:
        expected = {
            "get_airport_metrics",
            "get_airport_score",
            "compare_airports",
            "rank_airports",
            "rank_region",
            "get_long_haul_percentage",
            "get_unmet_demand",
            "simulate_airport_growth",
            "explain_congestion",
            "explain_unmet_demand",
            "explain_capacity_pressure",
            "rank_by_metric",
            "get_bts_delay_metrics",
            "compare_bts_airport_delays",
            "get_bts_delay_causes",
            "get_bts_delay_trend",
        }
        assert expected == set(TOOLS)


# ==================================================================
# Individual tools via execute()
# ==================================================================


class TestGetAirportMetrics:
    def test_returns_metrics(self) -> None:
        call = ToolCall(name="get_airport_metrics", arguments={"code": "BOS"})
        result = execute(call, _universe())
        assert isinstance(result, MetricsResult)
        assert result.airports == ["BOS"]
        assert result.metrics.airport_code == "BOS"

    def test_missing_airport(self) -> None:
        call = ToolCall(name="get_airport_metrics", arguments={"code": "PWM"})
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)
        assert "PWM" in result.reason


class TestGetAirportScore:
    def test_returns_score(self) -> None:
        call = ToolCall(name="get_airport_score", arguments={"code": "BOS"})
        result = execute(call, _universe())
        assert isinstance(result, ScoreResult)
        assert result.score.airport_code == "BOS"

    def test_missing_airport(self) -> None:
        call = ToolCall(name="get_airport_score", arguments={"code": "PWM"})
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)


class TestCompareAirports:
    def test_two_airports(self) -> None:
        call = ToolCall(
            name="compare_airports", arguments={"codes": ["BOS", "LAX"]}
        )
        result = execute(call, _universe())
        assert isinstance(result, ComparisonResult)
        assert len(result.rows) == 2
        assert result.airports == ["BOS", "LAX"]

    def test_missing_one_airport(self) -> None:
        call = ToolCall(
            name="compare_airports", arguments={"codes": ["BOS", "PWM"]}
        )
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)
        assert "PWM" in result.reason


class TestRankAirports:
    def test_rank_two(self) -> None:
        call = ToolCall(
            name="rank_airports", arguments={"codes": ["BOS", "LAX"]}
        )
        result = execute(call, _universe())
        assert isinstance(result, RankingResult)
        assert len(result.ranked) == 2

    def test_descending_order(self) -> None:
        call = ToolCall(
            name="rank_airports", arguments={"codes": ["BOS", "LAX"]}
        )
        result = execute(call, _universe())
        assert isinstance(result, RankingResult)
        scores = [
            s.opportunity_score.value
            for s in result.ranked
            if isinstance(s.opportunity_score, Present)
        ]
        assert scores == sorted(scores, reverse=True)


class TestRankRegion:
    def test_new_england(self) -> None:
        call = ToolCall(name="rank_region", arguments={"region": "new_england"})
        result = execute(call, _universe())
        assert isinstance(result, RankingResult)
        assert result.region == "new_england"
        for s in result.ranked:
            assert s.airport_code == "BOS"

    def test_unknown_region_rejected_by_validation(self) -> None:
        call = ToolCall(name="rank_region", arguments={"region": "mars"})
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)


class TestGetLongHaulPercentage:
    def test_absent_long_haul_with_proxies(self) -> None:
        u = _universe()
        # Add proxies to BOS
        from app.models.metrics import Present, Live, Absent
        origin = Live(source="BTS T-100", period="2023", fetched_at="now")
        u.dossiers["BOS"] = u.dossiers["BOS"].model_copy(
            update={
                "long_haul_pct": Absent(reason="NOT_PUBLISHED", detail="test", attempted=()),
                "metrics": u.dossiers["BOS"].metrics.model_copy(
                    update={
                        "international_departures": Present[int](value=10, origin=origin),
                        "total_departures": Present[int](value=100, origin=origin),
                        "average_flight_distance_sm": Present[float](value=1500.0, origin=origin),
                    }
                )
            }
        )
        call = ToolCall(name="get_long_haul_percentage", arguments={"code": "BOS"})
        result = execute(call, u)
        assert isinstance(result, LongHaulResult)
        assert isinstance(result.long_haul_pct, Absent)
        assert result.long_haul_pct.reason == "NOT_PUBLISHED"
        assert result.international_departures == 10.0
        assert result.international_departure_share_pct == 10.0
        assert result.live_average_distance_miles == 1500.0
        assert "Live proxies" in result.basis

    def test_present_long_haul_with_summary(self) -> None:
        u = _universe()
        from app.models.metrics import Present, Live
        from app.analytics.long_haul import LongHaulSummary
        origin = Live(source="BTS T-100 Segment", period="2023", fetched_at="now")
        summary = LongHaulSummary(
            pct=25.0,
            total_departures=100.0,
            long_haul_departures=25.0,
            unique_destinations=10,
            long_haul_destinations=2,
            average_distance_miles=2000.0,
            max_distance_miles=3500.0,
            top_long_haul_routes=[],
            start_year=2023,
            end_year=2023,
        )
        u.dossiers["BOS"] = u.dossiers["BOS"].model_copy(
            update={
                "long_haul_pct": Present[float](value=25.0, origin=origin),
                "long_haul_summary": summary,
            }
        )
        call = ToolCall(name="get_long_haul_percentage", arguments={"code": "BOS"})
        result = execute(call, u)
        assert isinstance(result, LongHaulResult)
        assert isinstance(result.long_haul_pct, Present)
        assert result.long_haul_pct.value == 25.0
        assert result.average_distance_miles == 2000.0
        assert "Long-haul from bulk file" in result.basis


class TestGetUnmetDemand:
    def test_returns_datum(self) -> None:
        call = ToolCall(name="get_unmet_demand", arguments={"code": "BOS"})
        result = execute(call, _universe())
        assert isinstance(result, UnmetDemandResult)
        assert isinstance(result.unmet_demand_index, Present)


class TestSimulateAirportGrowth:
    def test_positive_growth(self) -> None:
        call = ToolCall(
            name="simulate_airport_growth",
            arguments={"code": "BOS", "growth_pct": 0.05},
        )
        result = execute(call, _universe())
        assert isinstance(result, SimulationResult)
        assert result.growth_adjustment == 0.05
        assert result.baseline_score.airport_code == "BOS"

    def test_missing_airport(self) -> None:
        call = ToolCall(
            name="simulate_airport_growth",
            arguments={"code": "PWM", "growth_pct": 0.05},
        )
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)


# ==================================================================
# execute() edge cases
# ==================================================================


class TestExecuteEdgeCases:
    def test_unknown_tool(self) -> None:
        call = ToolCall(name="nonexistent", arguments={})
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)
        assert result.tool_name == "nonexistent"

    def test_invalid_args(self) -> None:
        call = ToolCall(
            name="get_airport_score", arguments={"code": "INVALID"}
        )
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)
        assert result.tool_name == "get_airport_score"

    def test_never_raises(self) -> None:
        call = ToolCall(name="get_airport_score", arguments={"code": 12345})
        result = execute(call, _universe())
        assert isinstance(result, ToolRejection)


# ==================================================================
# ChatResponse.assemble
# ==================================================================


class TestAssemble:
    def _score_ev(self) -> ScoreResult:
        u = _universe()
        return ScoreResult(
            airports=["BOS"], snapshot_at=_SNAPSHOT, score=u.scores["BOS"]
        )

    def test_single_score(self) -> None:
        ev = self._score_ev()
        resp = ChatResponse.assemble("BOS looks strong.", [ev], "this_turn")
        assert resp.message == "BOS looks strong."
        assert resp.airports == ["BOS"]
        assert "BOS" in resp.scores
        assert resp.analysis_type == "score"
        assert resp.evidence_origin == "this_turn"
        assert resp.confidence in ("HIGH", "MEDIUM", "LOW")

    def test_dedup_sources(self) -> None:
        ev = self._score_ev()
        resp = ChatResponse.assemble("ok", [ev, ev], "this_turn")
        assert len(resp.sources) == len(set(resp.sources))

    def test_extra_warnings_appended(self) -> None:
        ev = self._score_ev()
        resp = ChatResponse.assemble(
            "ok", [ev], "this_turn", extra_warnings=["stale data"]
        )
        assert "stale data" in resp.warnings

    def test_rejection_produces_warning(self) -> None:
        rej = ToolRejection(
            airports=["PWM"],
            snapshot_at=_SNAPSHOT,
            tool_name="get_airport_score",
            reason="not in universe",
        )
        resp = ChatResponse.assemble("hmm", [rej], "this_turn")
        assert any("not in universe" in w for w in resp.warnings)
        assert resp.analysis_type is None

    def test_empty_evidence(self) -> None:
        resp = ChatResponse.assemble("hello", [], "none")
        assert resp.airports == []
        assert resp.scores == {}
        assert resp.confidence == "LOW"
        assert resp.evidence_origin == "none"

    def test_comparison_evidence(self) -> None:
        u = _universe()
        from app.models.chat import ComparisonRow

        rows = [
            ComparisonRow(
                airport_code="BOS",
                score=u.scores["BOS"],
                metrics=u.dossiers["BOS"].metrics,
            ),
            ComparisonRow(
                airport_code="LAX",
                score=u.scores["LAX"],
                metrics=u.dossiers["LAX"].metrics,
            ),
        ]
        ev = ComparisonResult(
            airports=["BOS", "LAX"],
            snapshot_at=_SNAPSHOT,
            rows=rows,
            highest_congestion="BOS",
            highest_opportunity_score="LAX",
            period_warning=None,
        )
        resp = ChatResponse.assemble("compared", [ev], "this_turn")
        assert "BOS" in resp.scores
        assert "LAX" in resp.scores
        assert resp.analysis_type == "comparison"

    def test_confidence_is_minimum(self) -> None:
        u = _universe()
        bos_ev = ScoreResult(
            airports=["BOS"], snapshot_at=_SNAPSHOT, score=u.scores["BOS"]
        )
        lax_ev = ScoreResult(
            airports=["LAX"], snapshot_at=_SNAPSHOT, score=u.scores["LAX"]
        )
        resp = ChatResponse.assemble("both", [bos_ev, lax_ev], "this_turn")
        bos_conf = u.scores["BOS"].confidence
        lax_conf = u.scores["LAX"].confidence
        rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        expected = min(bos_conf, lax_conf, key=lambda c: rank[c])
        assert resp.confidence == expected
