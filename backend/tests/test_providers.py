from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.models.airport import IATA
from app.models.metrics import (
    Absent,
    AirportMetrics,
    Live,
    Present,
    Sample,
    _METRIC_FIELDS,
)
from app.models.score import ProviderFailure
from app.providers.base import (
    AviationProvider,
    ProviderOutcome,
    merge_outcomes,
)
from app.providers.aviation import OpenSkyProvider
from app.providers.opensky_auth import OpenSkyTokenManager
from app.providers.bts_on_time import BtsOnTimeProvider
from app.providers.faa_bulk import FaaAcaisFileProvider, FaaAtadsFileProvider
from app.providers.fallback import CompositeProvider, ContextComposite, SampleProvider
from app.services.airport_service import AirportCatalog, CoordinateLookup


def _live(source: str = "TestSrc", period: str = "2025-Q1") -> Live:
    return Live(source=source, period=period, fetched_at="2025-04-01T00:00:00Z")


def _sample(source: str = "BTS", period: str = "2024") -> Sample:
    return Sample(source=source, period=period, citation="test citation")


def _present_int(v: int, origin: Live | Sample | None = None) -> Present[int]:
    return Present[int](value=v, origin=origin or _live())


def _present_float(v: float, origin: Live | Sample | None = None) -> Present[float]:
    return Present[float](value=v, origin=origin or _live())


# ------------------------------------------------------------------
class TestBtsOnTimeProvider:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        import httpx
        from unittest.mock import AsyncMock

        async def fake_get(*args: object, **kwargs: object) -> httpx.Response:
            req = httpx.Request("GET", "https://data.transportation.gov/resource/xxxx-xxxx.json")
            return httpx.Response(
                200,
                json=[{"avg_dep_delay": "15.5", "pct_delayed_15": "0.25"}],
                request=req,
            )

        http = AsyncMock()
        http.get = fake_get

        provider = BtsOnTimeProvider(http, timeout_s=1.0)
        outcome = await provider.fetch(["BOS"])

        assert not outcome.failures
        assert "BOS" in outcome.fields
        assert outcome.fields["BOS"]["average_delay_minutes"].value == 15.5
        assert outcome.fields["BOS"]["delayed_flights_pct"].value == 25.0

class TestFaaBulkProviders:
    @pytest.mark.asyncio
    async def test_acais_provider(self, tmp_path: Path) -> None:
        import json
        data = {
            "BOS": {
                "passenger_volume": 100,
                "previous_passenger_volume": 90,
                "period": "CY2024",
                "fetched_at": "2024-01-01T00:00:00Z"
            }
        }
        p = tmp_path / "acais.json"
        p.write_text(json.dumps(data))
        
        provider = FaaAcaisFileProvider(path=p)
        outcome = await provider.fetch(["BOS"])
        assert not outcome.failures
        assert outcome.fields["BOS"]["passenger_volume"].value == 100
        
    @pytest.mark.asyncio
    async def test_atads_provider(self, tmp_path: Path) -> None:
        import json
        data = {
            "BOS": {
                "annual_operations": 500,
                "period": "CY2024",
                "fetched_at": "2024-01-01T00:00:00Z"
            }
        }
        p = tmp_path / "atads.json"
        p.write_text(json.dumps(data))
        
        provider = FaaAtadsFileProvider(path=p)
        outcome = await provider.fetch(["BOS"])
        assert not outcome.failures
        assert outcome.fields["BOS"]["annual_operations"].value == 500

# OpenSky provider
# ------------------------------------------------------------------


class _StubCoords:
    def icao_for(self, iata: str) -> str | None:
        return {"ANC": "PANC"}.get(iata)

    def get(self, icao: str) -> tuple[float, float] | None:
        table = {
            "PANC": (61.17, -149.99),
            "KJFK": (40.64, -73.78),
            "KSEA": (47.45, -122.31),
            "RJTT": (35.55, 139.78),
        }
        return table.get(icao)


class TestOpenSkyProvider:
    @pytest.mark.asyncio
    async def test_fetch_departures_sends_bearer(self) -> None:
        import httpx

        captured: dict[str, object] = {}

        async def fake_get(*args: object, **kwargs: object) -> httpx.Response:
            captured["headers"] = kwargs.get("headers")
            req = httpx.Request("GET", "https://opensky-network.org/api/flights/departure")
            return httpx.Response(200, json=[], request=req)

        http = AsyncMock()
        http.get = fake_get
        tm = AsyncMock(spec=OpenSkyTokenManager)
        tm.bearer_headers = AsyncMock(
            return_value={"Authorization": "Bearer test-token"}
        )
        provider = OpenSkyProvider(
            http, CoordinateLookup(), timeout_s=1.0, token_manager=tm
        )
        result, _meta = await provider._fetch_departures("PANC", 0, 1)
        assert result == []
        assert captured["headers"] == {"Authorization": "Bearer test-token"}

    @pytest.mark.asyncio
    async def test_fetch_counts_resolved_departures_only(self) -> None:
        import httpx

        flights = [
            {"icao24": "1", "firstSeen": 1, "estArrivalAirport": "KJFK"},
            {"icao24": "2", "firstSeen": 2, "estArrivalAirport": "KSEA"},
            {"icao24": "3", "firstSeen": 3, "estArrivalAirport": None},
            {"icao24": "4", "firstSeen": 4, "estArrivalAirport": "ZZZZ"},
        ]

        async def fake_get(*args: object, **kwargs: object) -> httpx.Response:
            req = httpx.Request("GET", "https://opensky-network.org/api/flights/departure")
            return httpx.Response(200, json=flights, request=req)

        http = AsyncMock()
        http.get = fake_get
        provider = OpenSkyProvider(
            http, _StubCoords(), timeout_s=1.0, token_manager=None, window_days=1, request_delay_s=0
        )
        outcome = await provider.fetch(["ANC"])  # type: ignore[arg-type]
        assert "ANC" in outcome.fields
        assert outcome.fields["ANC"]["total_departures"].value == 2
        assert outcome.fields["ANC"]["long_haul_flights"].value == 1

    @pytest.mark.asyncio
    async def test_fetch_fails_when_no_resolvable_destinations(self) -> None:
        import httpx

        flights = [
            {"icao24": "3", "firstSeen": 3, "estArrivalAirport": None},
            {"icao24": "4", "firstSeen": 4, "estArrivalAirport": "ZZZZ"}
        ]

        async def fake_get(*args: object, **kwargs: object) -> httpx.Response:
            req = httpx.Request("GET", "https://opensky-network.org/api/flights/departure")
            return httpx.Response(200, json=flights, request=req)

        http = AsyncMock()
        http.get = fake_get
        provider = OpenSkyProvider(
            http, _StubCoords(), timeout_s=1.0, token_manager=None, window_days=1, request_delay_s=0
        )
        outcome = await provider.fetch(["ANC"])  # type: ignore[arg-type]
        assert "ANC" not in outcome.fields
        assert any("resolvable destination" in w for w in outcome.warnings.get("ANC", []))


# ------------------------------------------------------------------
# ProviderOutcome + merge_outcomes
# ------------------------------------------------------------------


class TestProviderOutcome:
    def test_empty_outcome(self) -> None:
        o = ProviderOutcome(fields={}, failures=[])
        assert o.fields == {}
        assert o.failures == []

    def test_outcome_with_fields(self) -> None:
        o = ProviderOutcome(
            fields={
                "BOS": {"passenger_volume": _present_int(20_000_000)},
            },
            failures=[],
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
        outcome = ProviderOutcome(fields=fields, failures=[])
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
        )
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]
        m = result["BOS"]
        assert isinstance(m.annual_operations, Absent)

    def test_missing_field_with_failure_records_provider(self) -> None:
        outcome = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(1_000_000)}},
            failures=[ProviderFailure(provider="OpenSky", error="timeout")],
        )
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]
        m = result["BOS"]
        assert isinstance(m.annual_operations, Absent)
        assert m.annual_operations.reason == "PROVIDER_FAILED"
        assert "OpenSky" in m.annual_operations.attempted

    def test_first_outcome_takes_priority(self) -> None:
        o1 = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(999)}},
            failures=[],
        )
        o2 = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(111)}},
            failures=[],
        )
        result = merge_outcomes(["BOS"], [o1, o2])  # type: ignore[arg-type]
        assert isinstance(result["BOS"].passenger_volume, Present)
        assert result["BOS"].passenger_volume.value == 999

    def test_second_outcome_fills_gaps(self) -> None:
        o1 = ProviderOutcome(
            fields={"BOS": {"passenger_volume": _present_int(999)}},
            failures=[],
        )
        o2 = ProviderOutcome(
            fields={"BOS": {"annual_operations": _present_int(400_000)}},
            failures=[],
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
        )
        result = merge_outcomes(["BOS", "LAX"], [o])  # type: ignore[arg-type]
        assert "BOS" in result
        assert "LAX" in result

    def test_unknown_code_all_absent(self) -> None:
        o = ProviderOutcome(fields={}, failures=[])
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
        )
        result = merge_outcomes(["BOS"], [outcome])  # type: ignore[arg-type]
        m = result["BOS"]
        assert m.completeness_score == pytest.approx(2 / len(_METRIC_FIELDS))


# ------------------------------------------------------------------
# CoordinateLookup
# ------------------------------------------------------------------


class TestCoordinateLookup:
    def test_get_existing_icao(self) -> None:
        coords = CoordinateLookup()
        result = coords.get("KBOS")
        assert result is not None
        lat, lon = result
        assert 42.0 < lat < 43.0
        assert -72.0 < lon < -70.0

    def test_get_missing_icao(self) -> None:
        coords = CoordinateLookup()
        assert coords.get("ZZZZ") is None

    def test_icao_for_iata(self) -> None:
        coords = CoordinateLookup()
        assert coords.icao_for("BOS") == "KBOS"
        assert coords.icao_for("LAX") == "KLAX"
        assert coords.icao_for("ANC") == "PANC"

    def test_icao_for_unknown(self) -> None:
        coords = CoordinateLookup()
        assert coords.icao_for("ZZZ") is None

    def test_international_airports_present(self) -> None:
        coords = CoordinateLookup()
        assert coords.get("EGLL") is not None  # London Heathrow

    def test_ourairports_resolves_tokyo_haneda(self) -> None:
        coords = CoordinateLookup()
        assert coords.get("RJTT") is not None


# ------------------------------------------------------------------
# AirportCatalog
# ------------------------------------------------------------------


class TestAirportCatalog:
    def test_get_existing(self) -> None:
        catalog = AirportCatalog()
        airport = catalog.get("BOS")  # type: ignore[arg-type]
        assert airport is not None
        assert airport.iata_code == "BOS"
        assert airport.icao_code == "KBOS"

    def test_get_missing(self) -> None:
        catalog = AirportCatalog()
        assert catalog.get("ZZZ") is None  # type: ignore[arg-type]

    def test_codes_returns_all(self) -> None:
        catalog = AirportCatalog()
        codes = catalog.codes
        assert "BOS" in codes
        assert "LAX" in codes
        assert len(codes) >= 9


# ------------------------------------------------------------------
# SampleProvider
# ------------------------------------------------------------------


class TestSampleProvider:
    @pytest.mark.asyncio
    async def test_returns_present_for_known_code(self) -> None:
        provider = SampleProvider()
        outcome = await provider.fetch(["BOS"])  # type: ignore[arg-type]
        assert "BOS" in outcome.fields
        assert isinstance(outcome.fields["BOS"]["passenger_volume"], Present)

    @pytest.mark.asyncio
    async def test_returns_sample_origin(self) -> None:
        provider = SampleProvider()
        outcome = await provider.fetch(["BOS"])  # type: ignore[arg-type]
        pv = outcome.fields["BOS"]["passenger_volume"]
        assert isinstance(pv, Present)
        assert isinstance(pv.origin, Sample)

    @pytest.mark.asyncio
    async def test_unknown_code_becomes_failure(self) -> None:
        provider = SampleProvider()
        outcome = await provider.fetch(["ZZZ"])  # type: ignore[arg-type]
        assert len(outcome.failures) == 1
        assert outcome.failures[0].provider == "SampleData"

    @pytest.mark.asyncio
    async def test_multiple_codes(self) -> None:
        provider = SampleProvider()
        outcome = await provider.fetch(["BOS", "LAX", "JFK"])  # type: ignore[arg-type]
        assert len(outcome.fields) == 3


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
        return ProviderOutcome(fields=self._fields, failures=[])


class _FailingProvider:
    @property
    def name(self) -> str:
        return "Failing"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        raise RuntimeError("network down")


class TestCompositeProvider:
    @pytest.mark.asyncio
    async def test_live_results_come_first(self) -> None:
        live = _StubProvider(
            "LiveTest",
            {"BOS": {"passenger_volume": _present_int(42, _live("LiveSrc"))}},
        )
        sample = SampleProvider()
        composite = CompositeProvider(live=[live], sample=sample)
        outcomes = await composite.fetch(["BOS"])  # type: ignore[arg-type]
        assert len(outcomes) == 2
        assert "BOS" in outcomes[0].fields
        assert outcomes[0].fields["BOS"]["passenger_volume"].value == 42

    @pytest.mark.asyncio
    async def test_failing_live_produces_failure(self) -> None:
        sample = SampleProvider()
        composite = CompositeProvider(live=[_FailingProvider()], sample=sample)  # type: ignore[list-item]
        outcomes = await composite.fetch(["BOS"])  # type: ignore[arg-type]
        assert any(
            f.provider == "Failing" for o in outcomes for f in o.failures
        )

    @pytest.mark.asyncio
    async def test_sample_always_last(self) -> None:
        live = _StubProvider("Live", {})
        sample = SampleProvider()
        composite = CompositeProvider(live=[live], sample=sample)
        outcomes = await composite.fetch(["BOS"])  # type: ignore[arg-type]
        last = outcomes[-1]
        assert "BOS" in last.fields
        pv = last.fields["BOS"]["passenger_volume"]
        assert isinstance(pv.origin, Sample)


# ------------------------------------------------------------------
# AviationProvider protocol
# ------------------------------------------------------------------


class TestAviationProviderProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        stub = _StubProvider("test", {})
        assert isinstance(stub, AviationProvider)

    def test_sample_satisfies_protocol(self) -> None:
        sample = SampleProvider()
        assert isinstance(sample, AviationProvider)
