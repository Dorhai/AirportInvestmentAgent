from __future__ import annotations

import logging

import pytest

from app.models.metrics import (
    Derived,
    Live,
    Proxy,
    Sample,
    fold_origins,
)


def _live(source: str = "FAA", period: str = "2025-Q1") -> Live:
    return Live(source=source, period=period, fetched_at="2025-04-01T00:00:00Z")


def _sample(source: str = "BTS", period: str = "2024") -> Sample:
    return Sample(source=source, period=period, citation="BTS T-100 2024")


class TestFoldOrigins:
    def test_two_live_returns_derived_with_live_freshness(self) -> None:
        result = fold_origins(
            _live("FAA"), _live("CIRIUM"), method="weighted_avg"
        )
        assert isinstance(result, Derived)
        assert result.freshness == "live"
        assert set(result.sources) == {"FAA", "CIRIUM"}

    def test_sample_degrades_freshness(self) -> None:
        result = fold_origins(_sample(), method="passthrough")
        assert isinstance(result, Derived)
        assert result.freshness == "sample"

    def test_mixed_freshness(self) -> None:
        result = fold_origins(_live(), _sample(), method="blend")
        assert isinstance(result, Derived)
        assert result.freshness == "mixed"

    def test_proxy_flag_returns_proxy(self) -> None:
        result = fold_origins(
            _live(),
            method="regression",
            proxy=True,
            assumption="Linear correlation with GDP",
        )
        assert isinstance(result, Proxy)
        assert result.assumption == "Linear correlation with GDP"
        assert result.freshness == "live"

    def test_proxy_is_sticky(self) -> None:
        inner_proxy = Proxy(
            method="est",
            inputs=("live",),
            assumption="growth=3%",
            period="2025-Q1",
            sources=("FAA",),
            freshness="live",
        )
        result = fold_origins(inner_proxy, _live("CIRIUM"), method="combine")
        assert isinstance(result, Proxy), "proxy should be sticky through nesting"
        assert "FAA" in result.sources
        assert "CIRIUM" in result.sources

    def test_periods_merge_distinct(self) -> None:
        result = fold_origins(
            _live(period="2025-Q1"),
            _live(period="2025-Q2"),
            method="concat",
        )
        assert result.period == "2025-Q1; 2025-Q2"

    def test_duplicate_periods_deduplicated(self) -> None:
        result = fold_origins(
            _live(period="2025-Q1"),
            _live(period="2025-Q1"),
            method="avg",
        )
        assert result.period == "2025-Q1"

    def test_period_mismatch_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            fold_origins(
                _live(period="2025-Q1"),
                _sample(period="2024"),
                method="blend",
            )
        assert any("Mismatched periods" in msg for msg in caplog.messages)

    def test_sources_are_deduplicated(self) -> None:
        result = fold_origins(
            _live("FAA"), _live("FAA"), method="avg"
        )
        assert result.sources == ("FAA",)

    def test_nested_derived_sources_propagate(self) -> None:
        inner = fold_origins(_live("FAA"), _sample("BTS"), method="inner")
        result = fold_origins(inner, _live("CIRIUM"), method="outer")
        assert "FAA" in result.sources
        assert "BTS" in result.sources
        assert "CIRIUM" in result.sources
