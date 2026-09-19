from __future__ import annotations

import pytest

from app.analytics.capacity import calculate_capacity_pressure
from app.analytics.congestion import calculate_congestion_score, calculate_delay_pressure
from app.analytics.demand import calculate_passenger_growth
from app.analytics.opportunity import calculate_unmet_demand_index
from app.models.airport import Airport
from app.models.metrics import (
    Absent,
    AirportDossier,
    AirportMetrics,
    DatumFloat,
    DatumInt,
    Derived,
    Live,
    Present,
    Proxy,
    Sample,
)
from app.models.score import AirportScore, PeerStats, ProviderFailure
from app.scoring.expansion_score import (
    SCORING_WEIGHTS,
    calculate_confidence,
    compare,
    rank,
    score_dossier,
)
from app.scoring.normalization import clamp_score, normalize_min_max, normalize_percentage


# ------------------------------------------------------------------
# Shared fixtures
# ------------------------------------------------------------------


def _live(source: str = "FAA", period: str = "2025-Q1") -> Live:
    return Live(source=source, period=period, fetched_at="2025-04-01T00:00:00Z")


def _sample(source: str = "BTS", period: str = "2024") -> Sample:
    return Sample(source=source, period=period, citation="BTS T-100 2024")


def _absent(reason: str = "NOT_PUBLISHED") -> Absent:
    return Absent(reason=reason, detail="test", attempted=("test_provider",))  # type: ignore[arg-type]


def _present_int(v: int, origin: Live | Sample | None = None) -> Present[int]:
    return Present[int](value=v, origin=origin or _live())


def _present_float(v: float, origin: Live | Sample | None = None) -> Present[float]:
    return Present[float](value=v, origin=origin or _live())


_PEER_STATS = PeerStats(
    bounds={
        "annual_operations": (50_000.0, 500_000.0),
        "passenger_volume": (1_000_000.0, 50_000_000.0),
        "demand_growth": (0.0, 0.15),
        "pax_per_operation": (50.0, 200.0),
    },
    universe_codes=("BOS", "LAX", "JFK"),
)


def _make_metrics(
    *,
    pax: DatumInt | None = None,
    prev_pax: DatumInt | None = None,
    ops: DatumInt | None = None,
    delayed: DatumFloat | None = None,
    avg_delay: DatumFloat | None = None,
    lh: DatumInt | None = None,
    departures: DatumInt | None = None,
) -> AirportMetrics:
    return AirportMetrics(
        airport_code="BOS",
        passenger_volume=pax or _present_int(20_000_000),
        previous_passenger_volume=prev_pax or _present_int(18_000_000),
        annual_operations=ops or _present_int(200_000),
        delayed_flights_pct=delayed or _present_float(22.0),
        average_delay_minutes=avg_delay or _present_float(18.0),
        long_haul_flights=lh or _present_int(5000),
        total_departures=departures or _present_int(100_000),
    )


def _make_airport() -> Airport:
    return Airport(
        iata_code="BOS",
        icao_code="KBOS",
        name="Boston Logan",
        city="Boston",
        state="MA",
        latitude=42.3656,
        longitude=-71.0096,
    )


# ==================================================================
# Normalization
# ==================================================================


class TestNormalizeMinMax:
    def test_midpoint(self) -> None:
        assert normalize_min_max(50.0, 0.0, 100.0) == pytest.approx(50.0)

    def test_at_lo(self) -> None:
        assert normalize_min_max(0.0, 0.0, 100.0) == pytest.approx(0.0)

    def test_at_hi(self) -> None:
        assert normalize_min_max(100.0, 0.0, 100.0) == pytest.approx(100.0)

    def test_below_lo_clamped(self) -> None:
        assert normalize_min_max(-10.0, 0.0, 100.0) == 0.0

    def test_above_hi_clamped(self) -> None:
        assert normalize_min_max(200.0, 0.0, 100.0) == 100.0

    def test_equal_bounds_returns_50(self) -> None:
        assert normalize_min_max(42.0, 42.0, 42.0) == 50.0


class TestNormalizePercentage:
    def test_within_range(self) -> None:
        assert normalize_percentage(55.0) == 55.0

    def test_below_zero(self) -> None:
        assert normalize_percentage(-5.0) == 0.0

    def test_above_hundred(self) -> None:
        assert normalize_percentage(120.0) == 100.0


class TestClampScore:
    def test_normal(self) -> None:
        assert clamp_score(72.345) == 72.3

    def test_rounds_up(self) -> None:
        assert clamp_score(72.36) == 72.4

    def test_below_zero(self) -> None:
        assert clamp_score(-10.0) == 0.0

    def test_above_hundred(self) -> None:
        assert clamp_score(150.0) == 100.0


# ==================================================================
# Demand
# ==================================================================


class TestPassengerGrowth:
    def test_positive_growth(self) -> None:
        result = calculate_passenger_growth(
            _present_int(110), _present_int(100)
        )
        assert isinstance(result, Present)
        assert result.value == pytest.approx(0.1)
        assert isinstance(result.origin, Derived)

    def test_negative_growth(self) -> None:
        result = calculate_passenger_growth(
            _present_int(90), _present_int(100)
        )
        assert isinstance(result, Present)
        assert result.value == pytest.approx(-0.1)

    def test_previous_zero_returns_absent(self) -> None:
        result = calculate_passenger_growth(
            _present_int(100), _present_int(0)
        )
        assert isinstance(result, Absent)
        assert result.reason == "OUT_OF_SCOPE"
        assert "previous" in result.detail

    def test_previous_negative_returns_absent(self) -> None:
        result = calculate_passenger_growth(
            _present_int(100), _present_int(-5)
        )
        assert isinstance(result, Absent)
        assert result.reason == "OUT_OF_SCOPE"

    def test_absent_current(self) -> None:
        result = calculate_passenger_growth(_absent(), _present_int(100))
        assert isinstance(result, Absent)
        assert result.reason == "NOT_PUBLISHED"

    def test_absent_previous(self) -> None:
        result = calculate_passenger_growth(_present_int(100), _absent())
        assert isinstance(result, Absent)
        assert result.reason == "NOT_PUBLISHED"

    def test_both_absent_combines_attempted(self) -> None:
        a1 = Absent(reason="NOT_PUBLISHED", detail="a", attempted=("FAA",))
        a2 = Absent(reason="NOT_PUBLISHED", detail="b", attempted=("BTS",))
        result = calculate_passenger_growth(a1, a2)
        assert isinstance(result, Absent)
        assert "FAA" in result.attempted
        assert "BTS" in result.attempted

    def test_origin_folds_both_sources(self) -> None:
        result = calculate_passenger_growth(
            _present_int(110, _live("FAA")),
            _present_int(100, _sample("BTS")),
        )
        assert isinstance(result, Present)
        assert isinstance(result.origin, Derived)
        assert "FAA" in result.origin.sources
        assert "BTS" in result.origin.sources


# ==================================================================
# Delay pressure
# ==================================================================


class TestDelayPressure:
    def test_both_present(self) -> None:
        result = calculate_delay_pressure(
            _present_float(30.0), _present_float(20.0)
        )
        assert isinstance(result, Present)
        assert 0.0 <= result.value <= 100.0

    def test_only_delay_pct_present(self) -> None:
        result = calculate_delay_pressure(_present_float(50.0), _absent())
        assert isinstance(result, Present)
        assert result.value == pytest.approx(50.0)

    def test_only_avg_delay_present(self) -> None:
        result = calculate_delay_pressure(_absent(), _present_float(30.0))
        assert isinstance(result, Present)
        assert 0.0 <= result.value <= 100.0

    def test_both_absent(self) -> None:
        result = calculate_delay_pressure(_absent(), _absent())
        assert isinstance(result, Absent)
        assert result.reason == "NOT_PUBLISHED"


# ==================================================================
# Congestion
# ==================================================================


class TestCongestionScore:
    def test_all_present(self) -> None:
        m = _make_metrics()
        result = calculate_congestion_score(m, _PEER_STATS)
        assert isinstance(result, Present)
        assert 0.0 <= result.value <= 100.0
        assert isinstance(result.origin, Proxy)

    def test_gdp_bonus(self) -> None:
        m = _make_metrics()
        without = calculate_congestion_score(m, _PEER_STATS, gdp_active=False)
        with_gdp = calculate_congestion_score(m, _PEER_STATS, gdp_active=True)
        assert isinstance(without, Present) and isinstance(with_gdp, Present)
        assert with_gdp.value >= without.value

    def test_all_absent(self) -> None:
        m = _make_metrics(
            pax=_absent(),
            ops=_absent(),
            delayed=_absent(),
        )
        result = calculate_congestion_score(m, _PEER_STATS)
        assert isinstance(result, Absent)


# ==================================================================
# Capacity pressure
# ==================================================================


class TestCapacityPressure:
    def test_with_growth(self) -> None:
        m = _make_metrics()
        result = calculate_capacity_pressure(m, _present_float(0.05), _PEER_STATS)
        assert isinstance(result, Present)
        assert 0.0 <= result.value <= 100.0
        assert isinstance(result.origin, Proxy)

    def test_without_growth(self) -> None:
        m = _make_metrics()
        result = calculate_capacity_pressure(m, _absent(), _PEER_STATS)
        assert isinstance(result, Present)

    def test_absent_pax(self) -> None:
        m = _make_metrics(pax=_absent())
        result = calculate_capacity_pressure(m, _present_float(0.05), _PEER_STATS)
        assert isinstance(result, Absent)

    def test_zero_operations(self) -> None:
        m = _make_metrics(ops=_present_int(0))
        result = calculate_capacity_pressure(m, _present_float(0.05), _PEER_STATS)
        assert isinstance(result, Absent)
        assert result.reason == "OUT_OF_SCOPE"


# ==================================================================
# Unmet demand
# ==================================================================


class TestUnmetDemandIndex:
    def test_all_present(self) -> None:
        result = calculate_unmet_demand_index(
            _present_float(0.08),
            _present_float(40.0),
            _present_float(60.0),
            _PEER_STATS,
        )
        assert isinstance(result, Present)
        assert 0.0 <= result.value <= 100.0
        assert isinstance(result.origin, Proxy)

    def test_all_absent(self) -> None:
        result = calculate_unmet_demand_index(
            _absent(), _absent(), _absent(), _PEER_STATS
        )
        assert isinstance(result, Absent)

    def test_partial_absent_renormalises(self) -> None:
        result = calculate_unmet_demand_index(
            _present_float(0.08), _absent(), _present_float(50.0), _PEER_STATS
        )
        assert isinstance(result, Present)


# ==================================================================
# Expansion score — weights
# ==================================================================


class TestScoringWeights:
    def test_sum_to_one(self) -> None:
        assert sum(SCORING_WEIGHTS.values()) == pytest.approx(1.0)

    def test_expected_keys(self) -> None:
        assert set(SCORING_WEIGHTS) == {
            "demand_growth",
            "congestion",
            "delay_pressure",
            "capacity_pressure",
        }


# ==================================================================
# Expansion score — score_dossier
# ==================================================================


from app.models.context import AirportContext

def _make_dossier(metrics: AirportMetrics | None = None) -> AirportDossier:
    m = metrics or _make_metrics()
    return AirportDossier(
        airport=_make_airport(),
        metrics=m,
        passenger_growth=_present_float(0.08),
        long_haul_pct=_present_float(12.5),
        unmet_demand_index=_present_float(55.0),
        context=AirportContext(),
        snapshot_at="2025-04-01T00:00:00Z",
    )


class TestScoreDossier:
    def test_produces_airport_score(self) -> None:
        score = score_dossier(_make_dossier(), _PEER_STATS)
        assert isinstance(score, AirportScore)
        assert score.airport_code == "BOS"
        assert score.airport_name == "Boston Logan"

    def test_all_components_present(self) -> None:
        score = score_dossier(_make_dossier(), _PEER_STATS)
        assert isinstance(score.opportunity_score, Present)
        assert isinstance(score.demand_growth_score, Present)
        assert isinstance(score.congestion_score, Present)
        assert isinstance(score.delay_pressure_score, Present)
        assert isinstance(score.capacity_pressure_score, Present)

    def test_scores_within_range(self) -> None:
        score = score_dossier(_make_dossier(), _PEER_STATS)
        for field in (
            "opportunity_score",
            "demand_growth_score",
            "congestion_score",
            "delay_pressure_score",
            "capacity_pressure_score",
        ):
            datum = getattr(score, field)
            if isinstance(datum, Present):
                assert 0.0 <= datum.value <= 100.0, f"{field} out of range"

    def test_absent_growth_renormalises(self) -> None:
        d = AirportDossier(
            airport=_make_airport(),
            metrics=_make_metrics(),
            passenger_growth=_absent(),
            long_haul_pct=_present_float(12.5),
            unmet_demand_index=_present_float(55.0),
            context=AirportContext(),
            snapshot_at="2025-04-01T00:00:00Z",
        )
        score = score_dossier(d, _PEER_STATS)
        assert isinstance(score.demand_growth_score, Absent)
        assert isinstance(score.opportunity_score, Present)


# ==================================================================
# Confidence
# ==================================================================


class TestConfidence:
    def test_high_when_core_complete_but_long_haul_absent(self) -> None:
        m = AirportMetrics(
            airport_code="BOS",
            passenger_volume=_present_int(20_000_000),
            previous_passenger_volume=_present_int(18_000_000),
            annual_operations=_present_int(400_000),
            delayed_flights_pct=_present_float(20.0),
            average_delay_minutes=_present_float(15.0),
            long_haul_flights=_absent(),
            total_departures=_absent(),
        )
        components = {
            "demand_growth": _present_float(50.0),
            "congestion": _present_float(50.0),
            "delay_pressure": _present_float(50.0),
            "capacity_pressure": _present_float(50.0),
        }
        assert calculate_confidence(m, components) == "HIGH"

    def test_low_when_incomplete(self) -> None:
        m = _make_metrics()
        components = {
            "demand_growth": _present_float(50.0),
            "congestion": _absent(),
            "delay_pressure": _absent(),
            "capacity_pressure": _present_float(50.0),
        }
        assert calculate_confidence(m, components) == "LOW"

    def test_medium_when_partially_complete(self) -> None:
        m = _make_metrics()
        components = {
            "demand_growth": _present_float(50.0),
            "congestion": _present_float(50.0),
            "delay_pressure": _present_float(50.0),
            "capacity_pressure": _absent(),
        }
        assert calculate_confidence(m, components) == "MEDIUM"


# ==================================================================
# Rank & compare
# ==================================================================


class TestRank:
    def test_descending_order(self) -> None:
        s1 = score_dossier(_make_dossier(), _PEER_STATS)
        d2 = AirportDossier(
            airport=Airport(
                iata_code="LAX",
                icao_code="KLAX",
                name="Los Angeles",
                city="Los Angeles",
                state="CA",
                latitude=33.9425,
                longitude=-118.4081,
            ),
            metrics=AirportMetrics(
                airport_code="LAX",
                passenger_volume=_present_int(40_000_000),
                previous_passenger_volume=_present_int(35_000_000),
                annual_operations=_present_int(400_000),
                delayed_flights_pct=_present_float(30.0),
                average_delay_minutes=_present_float(25.0),
                long_haul_flights=_present_int(10000),
                total_departures=_present_int(200_000),
            ),
            passenger_growth=_present_float(0.14),
            long_haul_pct=_present_float(20.0),
            unmet_demand_index=_present_float(70.0),
            context=AirportContext(),
            snapshot_at="2025-04-01T00:00:00Z",
        )
        s2 = score_dossier(d2, _PEER_STATS)
        ranked = rank([s1, s2])
        assert isinstance(ranked[0].opportunity_score, Present)
        assert isinstance(ranked[1].opportunity_score, Present)
        assert ranked[0].opportunity_score.value >= ranked[1].opportunity_score.value

    def test_absent_sorts_last(self) -> None:
        s1 = score_dossier(_make_dossier(), _PEER_STATS)
        absent_dossier = AirportDossier(
            airport=Airport(
                iata_code="PWM",
                icao_code="KPWM",
                name="Portland Jetport",
                city="Portland",
                state="ME",
                latitude=43.6462,
                longitude=-70.3093,
            ),
            metrics=AirportMetrics(
                airport_code="PWM",
                passenger_volume=_absent(),
                previous_passenger_volume=_absent(),
                annual_operations=_absent(),
                delayed_flights_pct=_absent(),
                average_delay_minutes=_absent(),
                long_haul_flights=_absent(),
                total_departures=_absent(),
            ),
            passenger_growth=_absent(),
            long_haul_pct=_absent(),
            unmet_demand_index=_absent(),
            context=AirportContext(),
            snapshot_at="2025-04-01T00:00:00Z",
        )
        s2 = score_dossier(absent_dossier, _PEER_STATS)
        ranked = rank([s2, s1])
        assert isinstance(ranked[0].opportunity_score, Present)
        assert isinstance(ranked[-1].opportunity_score, Absent)


class TestCompare:
    def test_delta(self) -> None:
        s1 = score_dossier(_make_dossier(), _PEER_STATS)
        deltas = compare(s1, s1)
        for v in deltas.values():
            assert v == pytest.approx(0.0)

    def test_absent_yields_none(self) -> None:
        normal = score_dossier(_make_dossier(), _PEER_STATS)
        absent_dossier = AirportDossier(
            airport=Airport(
                iata_code="PWM",
                icao_code="KPWM",
                name="Portland Jetport",
                city="Portland",
                state="ME",
                latitude=43.6462,
                longitude=-70.3093,
            ),
            metrics=AirportMetrics(
                airport_code="PWM",
                passenger_volume=_absent(),
                previous_passenger_volume=_absent(),
                annual_operations=_absent(),
                delayed_flights_pct=_absent(),
                average_delay_minutes=_absent(),
                long_haul_flights=_absent(),
                total_departures=_absent(),
            ),
            passenger_growth=_absent(),
            long_haul_pct=_absent(),
            unmet_demand_index=_absent(),
            context=AirportContext(),
            snapshot_at="2025-04-01T00:00:00Z",
        )
        absent_score = score_dossier(absent_dossier, _PEER_STATS)
        deltas = compare(normal, absent_score)
        assert all(v is None for v in deltas.values())
