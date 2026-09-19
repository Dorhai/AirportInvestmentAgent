from __future__ import annotations

import pytest
import pandas as pd

from app.analytics.long_haul import (
    calculate_long_haul_percentage,
    haversine_miles,
    is_long_haul,
)

# Known city-pair distances (approximate statute miles)
# BOS → LAX ≈ 2611 mi
# BOS → LHR ≈ 3270 mi
# JFK → NRT ≈ 6760 mi


class TestHaversineMiles:
    def test_same_point_is_zero(self) -> None:
        assert haversine_miles(42.3656, -71.0096, 42.3656, -71.0096) == 0.0

    def test_bos_to_lax(self) -> None:
        dist = haversine_miles(42.3656, -71.0096, 33.9425, -118.4081)
        assert 2550 < dist < 2700

    def test_bos_to_london(self) -> None:
        dist = haversine_miles(42.3656, -71.0096, 51.4700, -0.4543)
        assert 3200 < dist < 3400

    def test_jfk_to_narita(self) -> None:
        dist = haversine_miles(40.6413, -73.7781, 35.7647, 140.3864)
        assert 6700 < dist < 6900

    def test_symmetry(self) -> None:
        d1 = haversine_miles(42.0, -71.0, 34.0, -118.0)
        d2 = haversine_miles(34.0, -118.0, 42.0, -71.0)
        assert d1 == pytest.approx(d2)


class TestIsLongHaul:
    def test_above_threshold(self) -> None:
        assert is_long_haul(3500.0) is True

    def test_exactly_at_threshold(self) -> None:
        assert is_long_haul(3000.0) is True

    def test_below_threshold(self) -> None:
        assert is_long_haul(2999.9) is False

    def test_custom_threshold(self) -> None:
        assert is_long_haul(2000.0, threshold=1500.0) is True
        assert is_long_haul(1000.0, threshold=1500.0) is False


class TestCalculateLongHaulPercentage:
    def test_empty_df(self) -> None:
        df = pd.DataFrame()
        res = calculate_long_haul_percentage(df, "ANC")
        assert res["percentage"] is None
        assert res["total_departures"] == 0.0

    def test_basic_calculation(self) -> None:
        # 100 total departures, 20 long-haul departures -> 20%
        df = pd.DataFrame({
            "origin": ["ANC", "ANC"],
            "destination": ["SEA", "NRT"],
            "distance_miles": [1500.0, 3500.0],
            "performed_departures": [80, 20],
        })
        res = calculate_long_haul_percentage(df, "ANC")
        assert res["percentage"] == pytest.approx(20.0)
        assert res["total_departures"] == 100.0
        assert res["long_haul_departures"] == 20.0

    def test_weighted_rows(self) -> None:
        # Route A: distance 3500, deps 80
        # Route B: distance 1000, deps 20
        # Expected = 80% (not 50%)
        df = pd.DataFrame({
            "origin": ["ANC", "ANC"],
            "destination": ["NRT", "SEA"],
            "distance_miles": [3500.0, 1000.0],
            "performed_departures": [80, 20],
        })
        res = calculate_long_haul_percentage(df, "ANC")
        assert res["percentage"] == pytest.approx(80.0)

    def test_zero_departures(self) -> None:
        df = pd.DataFrame({
            "origin": ["ANC"],
            "destination": ["SEA"],
            "distance_miles": [1500.0],
            "performed_departures": [0],
        })
        res = calculate_long_haul_percentage(df, "ANC")
        assert res["percentage"] is None

    def test_threshold_edges(self) -> None:
        df = pd.DataFrame({
            "origin": ["ANC", "ANC", "ANC"],
            "destination": ["A", "B", "C"],
            "distance_miles": [2999.0, 3000.0, 3001.0],
            "performed_departures": [10, 10, 10],
        })
        res = calculate_long_haul_percentage(df, "ANC", threshold_miles=3000.0)
        # 2 long haul (3000, 3001) out of 3 -> 66.66%
        assert res["percentage"] == pytest.approx(66.66666666666666)

    def test_origin_filtering(self) -> None:
        # Ensure ANC only includes Origin == ANC
        df = pd.DataFrame({
            "origin": ["ANC", "SEA"],
            "destination": ["SEA", "ANC"],
            "distance_miles": [3500.0, 3500.0],
            "performed_departures": [10, 50],
        })
        res = calculate_long_haul_percentage(df, "ANC")
        assert res["total_departures"] == 10.0
        assert res["percentage"] == pytest.approx(100.0)
