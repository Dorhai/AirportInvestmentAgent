from __future__ import annotations

import pytest

from app.analytics.congestion import calculate_congestion_score
from app.analytics.drivers import congestion_drivers
from app.models.metrics import Present
from app.models.score import PeerStats
from tests.test_scoring import _make_metrics, _present_float, _present_int


@pytest.fixture
def peers() -> PeerStats:
    return PeerStats(
        bounds={
            "annual_operations": (100_000.0, 500_000.0),
            "passenger_volume": (1_000_000.0, 50_000_000.0),
            "demand_growth": (0.0, 0.15),
        },
        universe_codes=("BOS", "LAX"),
    )


def test_congestion_drivers_match_score(peers: PeerStats) -> None:
    m = _make_metrics(
        ops=_present_int(200_000),
        pax=_present_int(5_000_000),
        delayed=_present_float(15.0),
    )
    score = calculate_congestion_score(m, peers)
    breakdown = congestion_drivers(m, peers)
    assert isinstance(score, Present) and isinstance(breakdown.score, Present)
    assert score.value == pytest.approx(breakdown.score.value)
    assert breakdown.highest_driver is not None
