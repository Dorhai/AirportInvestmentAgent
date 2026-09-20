import pytest
from app.analytics.long_haul import SegmentRow, summarize_long_haul

def test_summarize_long_haul():
    rows = [
        SegmentRow(origin="BOS", dest="JFK", distance_miles=187.0, departures=100.0, passengers=10000.0, year=2023, month=1, service_class="F"),
        SegmentRow(origin="BOS", dest="LHR", distance_miles=3265.0, departures=30.0, passengers=6000.0, year=2023, month=1, service_class="F"),
        SegmentRow(origin="BOS", dest="CDG", distance_miles=3254.0, departures=20.0, passengers=4000.0, year=2023, month=1, service_class="F"),
        SegmentRow(origin="BOS", dest="LAX", distance_miles=2611.0, departures=50.0, passengers=8000.0, year=2023, month=1, service_class="F"),
    ]
    
    summary = summarize_long_haul(rows)
    assert summary is not None
    assert summary.total_departures == 200.0
    assert summary.long_haul_departures == 50.0
    assert summary.pct == 25.0
    assert summary.unique_destinations == 4
    assert summary.long_haul_destinations == 2
    assert summary.max_distance_miles == 3265.0
    
    # Weighted average distance
    expected_avg = (187*100 + 3265*30 + 3254*20 + 2611*50) / 200.0
    assert summary.average_distance_miles == expected_avg
    
    assert len(summary.top_long_haul_routes) == 2
    assert summary.top_long_haul_routes[0]["destination"] == "LHR"
    assert summary.top_long_haul_routes[0]["departures"] == 30.0
    assert summary.top_long_haul_routes[1]["destination"] == "CDG"
    assert summary.top_long_haul_routes[1]["departures"] == 20.0

def test_summarize_long_haul_passenger_only():
    rows = [
        SegmentRow(origin="ANC", dest="NRT", distance_miles=3500.0, departures=10.0, passengers=0.0, year=2023, month=1, service_class="P"), # Cargo
        SegmentRow(origin="ANC", dest="SEA", distance_miles=1448.0, departures=50.0, passengers=8000.0, year=2023, month=1, service_class="F"), # Passenger
    ]
    
    summary = summarize_long_haul(rows, passenger_only=True)
    assert summary is not None
    assert summary.total_departures == 50.0
    assert summary.long_haul_departures == 0.0
    assert summary.pct == 0.0

def test_summarize_long_haul_threshold_edge():
    rows = [
        SegmentRow(origin="JFK", dest="SFO", distance_miles=2586.0, departures=10.0, passengers=1000.0, year=2023, month=1, service_class="F"),
        SegmentRow(origin="JFK", dest="XXX", distance_miles=3000.0, departures=10.0, passengers=1000.0, year=2023, month=1, service_class="F"),
    ]
    
    summary = summarize_long_haul(rows, threshold=3000.0)
    assert summary is not None
    assert summary.long_haul_departures == 10.0
    assert summary.pct == 50.0
