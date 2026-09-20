import pytest
from datetime import date
from app.analytics.t100 import (
    MonthlyTraffic,
    latest_complete_month,
    trailing_windows,
)

def test_latest_complete_month():
    rows = [
        MonthlyTraffic(code="BOS", month=date(2026, 4, 1), departures=1, passengers=1, seats=1, intl_departures=1),
        MonthlyTraffic(code="JFK", month=date(2026, 5, 1), departures=1, passengers=1, seats=1, intl_departures=1),
    ]
    assert latest_complete_month(rows) == date(2026, 5, 1)
    assert latest_complete_month([]) is None

def test_trailing_windows_complete():
    # 2 months windows
    rows = []
    # Current window: 2026-04, 2026-05
    # Previous window: 2026-02, 2026-03
    for m in range(2, 6):
        rows.append(MonthlyTraffic(
            code="BOS", month=date(2026, m, 1), departures=10, passengers=100, seats=120, intl_departures=2
        ))
    
    res = trailing_windows(rows, months=2)
    assert "BOS" in res
    comp = res["BOS"]
    assert comp.current.months == 2
    assert comp.current.passengers == 200
    assert comp.current.start == date(2026, 4, 1)
    assert comp.current.end == date(2026, 5, 1)
    
    assert comp.previous.months == 2
    assert comp.previous.passengers == 200
    assert comp.previous.start == date(2026, 2, 1)
    assert comp.previous.end == date(2026, 3, 1)
    
    assert comp.period_label == "2026-04..2026-05 vs 2026-02..2026-03"

def test_trailing_windows_incomplete():
    rows = []
    # Missing 2026-03
    for m in [2, 4, 5]:
        rows.append(MonthlyTraffic(
            code="BOS", month=date(2026, m, 1), departures=10, passengers=100, seats=120, intl_departures=2
        ))
    
    res = trailing_windows(rows, months=2)
    assert "BOS" not in res

def test_trailing_windows_weighted_distance():
    rows = [
        MonthlyTraffic(code="BOS", month=date(2026, 4, 1), departures=100, passengers=100, seats=120, intl_departures=2, avg_distance_sm=1000.0),
        MonthlyTraffic(code="BOS", month=date(2026, 5, 1), departures=200, passengers=100, seats=120, intl_departures=2, avg_distance_sm=2000.0),
        MonthlyTraffic(code="BOS", month=date(2026, 2, 1), departures=100, passengers=100, seats=120, intl_departures=2, avg_distance_sm=1000.0),
        MonthlyTraffic(code="BOS", month=date(2026, 3, 1), departures=100, passengers=100, seats=120, intl_departures=2, avg_distance_sm=1000.0),
    ]
    
    res = trailing_windows(rows, months=2)
    assert "BOS" in res
    comp = res["BOS"]
    
    # Weighted avg for current: (100*1000 + 200*2000) / 300 = 500000 / 300 = 1666.666...
    assert comp.current.avg_distance_sm == pytest.approx(1666.6666666666667)
    
    # Weighted avg for previous: (100*1000 + 100*1000) / 200 = 1000.0
    assert comp.previous.avg_distance_sm == 1000.0
