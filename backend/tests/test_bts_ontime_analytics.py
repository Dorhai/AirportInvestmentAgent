import pytest
from datetime import date

from app.analytics.bts_ontime import DelayBucket, aggregate_buckets, get_delay_causes, get_delay_trend

def test_aggregate_buckets():
    buckets = [
        DelayBucket(
            airport="LAX",
            direction="departures",
            date=date(2025, 1, 1),
            valid_flights=10,
            delayed_15=2,
            cancelled=1,
            diverted=0,
            delay_minutes=30.0,
            carrier_delay=10.0,
            weather_delay=0.0,
            nas_delay=20.0,
            security_delay=0.0,
            late_aircraft_delay=0.0
        ),
        DelayBucket(
            airport="LAX",
            direction="arrivals",
            date=date(2025, 1, 1),
            valid_flights=5,
            delayed_15=1,
            cancelled=0,
            diverted=0,
            delay_minutes=15.0,
            carrier_delay=0.0,
            weather_delay=0.0,
            nas_delay=15.0,
            security_delay=0.0,
            late_aircraft_delay=0.0
        )
    ]
    
    metrics = aggregate_buckets("LAX", buckets, date(2025, 1, 1), date(2025, 1, 1))
    
    assert metrics.airport == "LAX"
    assert metrics.total_flights == 16
    assert metrics.departure_delay_pct == 20.0
    assert metrics.arrival_delay_pct == 20.0
    assert metrics.average_departure_delay_minutes == 3.0
    assert metrics.average_arrival_delay_minutes == 3.0
    assert metrics.cancellation_pct == 1 / 16 * 100
    assert metrics.primary_delay_cause == "NAS"

def test_get_delay_causes():
    buckets = [
        DelayBucket(
            airport="LAX",
            direction="departures",
            date=date(2025, 1, 1),
            valid_flights=10,
            delayed_15=2,
            cancelled=1,
            diverted=0,
            delay_minutes=30.0,
            carrier_delay=10.0,
            weather_delay=0.0,
            nas_delay=20.0,
            security_delay=0.0,
            late_aircraft_delay=0.0
        )
    ]
    
    causes = get_delay_causes("LAX", buckets, date(2025, 1, 1), date(2025, 1, 1), "departures")
    
    assert causes.total_flights == 11
    assert causes.carrier_delay_pct == 33.33333333333333
    assert causes.nas_delay_pct == 66.66666666666666
    assert causes.primary_delay_cause == "NAS"
