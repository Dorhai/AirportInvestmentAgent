from __future__ import annotations

from collections.abc import Sequence
import pytest

from app.models.airport import IATA
from app.models.metrics import (
    Absent,
    AirportMetrics,
    Live,
    Present,
    _METRIC_FIELDS,
)
from app.models.score import ProviderFailure
from app.providers.base import (
    AviationProvider,
    ProviderOutcome,
    merge_outcomes,
)
from app.providers.composite import CompositeProvider

def _live(source: str = "TestSrc", period: str = "2025-Q1") -> Live:
    return Live(source=source, period=period, fetched_at="2025-04-01T00:00:00Z")

def _present_int(v: int, origin: Live | None = None) -> Present[int]:
    return Present[int](value=v, origin=origin or _live())

def _present_float(v: float, origin: Live | None = None) -> Present[float]:
    return Present[float](value=v, origin=origin or _live())


# ------------------------------------------------------------------
# ProviderOutcome + merge_outcomes
# ------------------------------------------------------------------

class TestProviderOutcome:
    def test_empty_outcome(self) -> None:
        o = ProviderOutcome(fields={}, failures=[], warnings={})
        assert o.fields == {}
        assert o.failures == []

    def test_outcome_with_fields(self) -> None:
        o = ProviderOutcome(
            fields={
                "BOS": {"passenger_volume": _present_int(20_000_000)},
            },
            failures=[],
            warnings={},
        )
        assert "BOS" in o.fields
        assert isinstance(o.fields["BOS"]["passenger_volume"], Present)


class TestMergeOutcomes:
    def test_single_outcome_all_fields(self) -> None:
        fields = {
            "BOS": {
                name: _present_int(100) if name != "delayed_flights_pct" and name != "average_delay_minutes"
                else _present_float(10.0)
                for name in _METRIC_FIELDS
            },
        }
        outcome = ProviderOutcome(fields=fields, failures=[], warnings={})
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]

        assert "BOS" in result
        m = result["BOS"]
        assert isinstance(m, AirportMetrics)
        assert isinstance(m.passenger_volume, Present)
        assert m.passenger_volume.value == 100

    def test_missing_field_becomes_absent(self) -> None:
        outcome = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(1_000_000)}},
            failures=[],
            warnings={},
        )
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]
        m = result["BOS"]
        assert isinstance(m.annual_operations, Absent)

    def test_missing_field_with_failure_records_provider(self) -> None:
        outcome = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(1_000_000)}},
            failures=[ProviderFailure(provider="TestProvider", error="timeout")],
            warnings={},
        )
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]
        m = result["BOS"]
        assert isinstance(m.annual_operations, Absent)
        assert m.annual_operations.reason == "PROVIDER_FAILED"
        assert "TestProvider" in m.annual_operations.attempted

    def test_first_outcome_takes_priority(self) -> None:
        o1 = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(999)}},
            failures=[],
            warnings={},
        )
        o2 = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(111)}},
            failures=[],
            warnings={},
        )
        result = merge_outcomes(["BOS"], [o1, o2])  # type: ignore[arg-type]
        assert isinstance(result["BOS"].passenger_volume, Present)
        assert result["BOS"].passenger_volume.value == 999

    def test_second_outcome_fills_gaps(self) -> None:
        o1 = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(999)}},
            failures=[],
            warnings={},
        )
        o2 = ProviderOutcome(
            fields={"BOS": {"annual_operations": _present_int(400_000)}},
            failures=[],
            warnings={},
        )
        result = merge_outcomes(["BOS"], [o1, o2])  # type: ignore[arg-type]
        assert isinstance(result["BOS"].passenger_volume, Present)
        assert result["BOS"].passenger_volume.value == 999
        assert isinstance(result["BOS"].annual_operations, Present)
        assert result["BOS"].annual_operations.value == 400_000

    def test_multiple_codes(self) -> None:
        o = ProviderOutcome(
            fields={
                "BOS": {"passenger_volume": _present_int(20_000_000)},
                "LAX": {"passenger_volume": _present_int(40_000_000)},
            },
            failures=[],
            warnings={},
        )
        result = merge_outcomes(["BOS", "LAX"], [o])  # type: ignore[arg-type]
        assert "BOS" in result
        assert "LAX" in result

    def test_unknown_code_all_absent(self) -> None:
        o = ProviderOutcome(fields={}, failures=[], warnings={})
        result = merge_outcomes(["BOS"], [o])  # type: ignore[arg-type]
        m = result["BOS"]
        for name in _METRIC_FIELDS:
            assert isinstance(getattr(m, name), Absent)

    def test_completeness_score_partial(self) -> None:
        outcome = ProviderOutcome(
            fields={
                "BOS": {
                    "passenger_volume": _present_int(20_000_000),
                    "annual_operations": _present_int(400_000),
                },
            },
            failures=[],
            warnings={},
        )
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]
        m = result["BOS"]
        assert m.completeness_score == pytest.approx(2 / len(_METRIC_FIELDS))


# ------------------------------------------------------------------
# CompositeProvider
# ------------------------------------------------------------------

class _StubProvider:
    def __init__(self, name: str, fields: dict[str, dict[str, Present]]) -> None:
        self._name = name
        self._fields = fields

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        return ProviderOutcome(fields=self._fields, failures=[], warnings={})


class _FailingProvider:
    @property
    def name(self) -> str:
        return "Failing"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        raise RuntimeError("network down")


class TestCompositeProvider:
    @pytest.mark.asyncio
    async def test_live_results(self) -> None:
        live = _StubProvider(
            "LiveTest",
            {"BOS": {"passenger_volume": _present_int(42, _live("LiveSrc"))}},
        )
        composite = CompositeProvider(providers=[live])
        outcomes = await composite.fetch(["BOS"])  # type: ignore[arg-type]
        assert len(outcomes) == 1
        assert "BOS" in outcomes[0].fields
        assert outcomes[0].fields["BOS"]["passenger_volume"].value == 42

    @pytest.mark.asyncio
    async def test_failing_live_produces_failure(self) -> None:
        composite = CompositeProvider(providers=[_FailingProvider()])  # type: ignore[list-item]
        outcomes = await composite.fetch(["BOS"])  # type: ignore[arg-type]
        assert any(
            f.provider == "Failing" for o in outcomes for f in o.failures
        )
