import pytest
from pathlib import Path
from datetime import date

from app.services.bts_ontime_service import BtsOnTimeService

def test_bts_ontime_service_load_from_csv_file():
    fixture_file = Path(__file__).parent / "fixtures" / "bts_ontime" / "sample.csv"
    service = BtsOnTimeService(fixture_file)
    service.load_sync()
    assert service.is_loaded
    assert service.get_airport_delay_metrics("LAX", direction="departures") is not None


def test_bts_ontime_service_load():
    fixture_dir = Path(__file__).parent / "fixtures" / "bts_ontime"
    
    service = BtsOnTimeService(fixture_dir)
    service.load_sync()
    
    assert service.is_loaded
    assert service.data_min_date == date(2025, 1, 1)
    assert service.data_max_date == date(2025, 1, 4)
    
    metrics = service.get_airport_delay_metrics("LAX", direction="departures")
    assert metrics is not None
    assert metrics.total_flights == 3
    assert metrics.cancellation_pct == 33.33333333333333
    assert metrics.departure_delay_pct == 50.0  # 1 delayed out of 2 valid
    assert metrics.average_departure_delay_minutes == 15.0  # 30 mins / 2 valid
    
    comp = service.compare_airport_delays("LAX", "SNA")
    assert comp is not None
    assert comp.airport_a.airport == "LAX"
    assert comp.airport_b.airport == "SNA"
    
    causes = service.get_delay_causes("LAX", direction="departures")
    assert causes is not None
    assert causes.primary_delay_cause == "Carrier"
    
    trend = service.get_delay_trend("LAX", direction="departures")
    assert trend is not None
    assert len(trend) == 1
    assert trend[0].year == 2025
    assert trend[0].month == 1
    assert trend[0].delay_pct == 50.0
