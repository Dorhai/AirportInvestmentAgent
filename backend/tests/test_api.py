"""Tests for airport API routes with a mocked AnalysisService."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.airport import Airport
from app.models.metrics import (
    Absent,
    AirportDossier,
    AirportMetrics,
    Live,
    Present,
    Sample,
)
from app.models.score import AirportScore, PeerStats, ProviderFailure
from app.scoring.expansion_score import score_dossier
from app.services.analysis_service import Universe


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _live(source: str = "FAA", period: str = "2025-Q1") -> Live:
    return Live(source=source, period=period, fetched_at="2025-04-01T00:00:00Z")


def _sample(source: str = "BTS", period: str = "2024") -> Sample:
    return Sample(source=source, period=period, citation="BTS T-100 2024")


def _absent(reason: str = "NOT_PUBLISHED") -> Absent:
    return Absent(reason=reason, detail="test", attempted=("test_provider",))  # type: ignore[arg-type]


def _present_int(v: int, origin=None) -> Present[int]:
    return Present[int](value=v, origin=origin or _live())


def _present_float(v: float, origin=None) -> Present[float]:
    return Present[float](value=v, origin=origin or _live())


_PEER_STATS = PeerStats(
    bounds={
        "annual_operations": (50_000.0, 500_000.0),
        "passenger_volume": (1_000_000.0, 50_000_000.0),
        "demand_growth": (0.0, 0.15),
        "pax_per_operation": (50.0, 200.0),
    },
    universe_codes=("BOS", "LAX"),
)


def _make_airport(code: str = "BOS", state: str = "MA") -> Airport:
    return Airport(
        iata_code=code,  # type: ignore[arg-type]
        icao_code=f"K{code}",
        name=f"{code} Airport",
        city=code,
        state=state,
        latitude=42.0,
        longitude=-71.0,
    )


def _make_metrics(code: str = "BOS") -> AirportMetrics:
    return AirportMetrics(
        airport_code=code,  # type: ignore[arg-type]
        passenger_volume=_present_int(20_000_000),
        previous_passenger_volume=_present_int(18_000_000),
        annual_operations=_present_int(200_000),
        delayed_flights_pct=_present_float(22.0),
        average_delay_minutes=_present_float(18.0),
        long_haul_flights=_present_int(5000),
        total_departures=_present_int(100_000),
    )


from app.models.context import AirportContext

def _make_dossier(code: str = "BOS", state: str = "MA") -> AirportDossier:
    return AirportDossier(
        airport=_make_airport(code, state),
        metrics=_make_metrics(code),
        passenger_growth=_present_float(0.08),
        long_haul_pct=_present_float(12.5),
        unmet_demand_index=_present_float(55.0),
        context=AirportContext(),
        snapshot_at="2025-04-01T00:00:00Z",
    )


def _build_universe() -> Universe:
    dossiers: dict[str, AirportDossier] = {
        "BOS": _make_dossier("BOS", "MA"),
        "LAX": _make_dossier("LAX", "CA"),
    }
    scores: dict[str, AirportScore] = {
        code: score_dossier(d, _PEER_STATS)
        for code, d in dossiers.items()
    }
    return Universe(
        snapshot_at="2025-04-01T00:00:00Z",
        dossiers=dossiers,
        scores=scores,
        peers=_PEER_STATS,
        failures=[],
    )


# ------------------------------------------------------------------
# Fixture: TestClient with mocked AnalysisService
# ------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    mock_service = AsyncMock()
    mock_service.universe = AsyncMock(return_value=_build_universe())

    app.state.analysis_service = mock_service
    return TestClient(app, raise_server_exceptions=False)


# ==================================================================
# Route: GET /api/airports/{code}
# ==================================================================


class TestGetAirportMetrics:
    def test_valid_code(self, client: TestClient) -> None:
        resp = client.get("/api/airports/BOS")
        assert resp.status_code == 200
        body = resp.json()
        assert "metrics" in body
        assert body["metrics"]["airport_code"] == "BOS"
        assert "passenger_volume" in body["metrics"]

    def test_lowercase_code(self, client: TestClient) -> None:
        resp = client.get("/api/airports/bos")
        assert resp.status_code == 200
        assert resp.json()["metrics"]["airport_code"] == "BOS"

    def test_unknown_code(self, client: TestClient) -> None:
        resp = client.get("/api/airports/XYZ")
        assert resp.status_code == 404
        assert "not a supported" in resp.json()["detail"]


# ==================================================================
# Route: GET /api/airports/{code}/score
# ==================================================================


class TestGetAirportScore:
    def test_valid_code(self, client: TestClient) -> None:
        resp = client.get("/api/airports/BOS/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["airport_code"] == "BOS"
        assert "opportunity_score" in body
        assert "confidence" in body

    def test_unknown_code(self, client: TestClient) -> None:
        resp = client.get("/api/airports/XYZ/score")
        assert resp.status_code == 404


# ==================================================================
# Route: POST /api/airports/compare
# ==================================================================


class TestCompareAirports:
    def test_two_airports(self, client: TestClient) -> None:
        resp = client.post(
            "/api/airports/compare",
            json={"airport_codes": ["BOS", "LAX"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["rows"]) == 2
        codes = {r["airport_code"] for r in body["rows"]}
        assert codes == {"BOS", "LAX"}

    def test_unknown_code_in_list(self, client: TestClient) -> None:
        resp = client.post(
            "/api/airports/compare",
            json={"airport_codes": ["BOS", "XYZ"]},
        )
        assert resp.status_code in (404, 422)

    def test_has_summary_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/api/airports/compare",
            json={"airport_codes": ["BOS", "LAX"]},
        )
        body = resp.json()
        assert "highest_congestion" in body
        assert "highest_opportunity_score" in body
        assert "period_warning" in body


# ==================================================================
# Route: GET /api/regions/{region}/ranking
# ==================================================================


class TestRegionRanking:
    def test_new_england(self, client: TestClient) -> None:
        resp = client.get("/api/regions/new_england/ranking")
        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "new_england"
        assert isinstance(body["ranked"], list)
        codes = [s["airport_code"] for s in body["ranked"]]
        assert "BOS" in codes

    def test_california(self, client: TestClient) -> None:
        resp = client.get("/api/regions/california/ranking")
        assert resp.status_code == 200
        body = resp.json()
        codes = [s["airport_code"] for s in body["ranked"]]
        assert "LAX" in codes

    def test_unknown_region(self, client: TestClient) -> None:
        resp = client.get("/api/regions/mars/ranking")
        assert resp.status_code == 404


# ==================================================================
# Route: GET /api/scoring/methodology
# ==================================================================

class TestGetScoringMethodology:
    def test_methodology(self, client: TestClient) -> None:
        resp = client.get("/api/scoring/methodology")
        assert resp.status_code == 200
        body = resp.json()
        assert "weights" in body
        assert "demand_growth" in body["weights"]
        weights = body["weights"]
        assert sum(weights.values()) == pytest.approx(1.0)
        assert len(body["rules"]) > 0

# ==================================================================
# Exception handling
# ==================================================================


class TestExceptionHandlers:
    def test_unknown_airport_error_format(self, client: TestClient) -> None:
        resp = client.get("/api/airports/XYZ")
        body = resp.json()
        assert "XYZ" in body["detail"]
        assert "not a supported" in body["detail"]

    def test_root_still_works(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["message"] == "AirportIQ API"

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
