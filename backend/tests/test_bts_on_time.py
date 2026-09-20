import pytest
from datetime import date
from unittest.mock import Mock

from app.providers.bts_ontime_bulk import BtsOnTimeBulkProvider
from app.services.bts_ontime_service import BtsOnTimeService
from app.analytics.bts_ontime import AirportDelayMetrics

@pytest.fixture
def mock_service():
    service = Mock(spec=BtsOnTimeService)
    service.is_loaded = True
    service.data_max_date = date(2026, 6, 30)
    service.loaded_at = "2026-09-20T12:00:00Z"
    
    metrics = AirportDelayMetrics(
        airport="BOS",
        period="2025-07 to 2026-06",
        total_flights=1000,
        departure_delay_pct=17.5,
        arrival_delay_pct=15.0,
        average_departure_delay_minutes=13.75,
        average_arrival_delay_minutes=12.0,
        cancellation_pct=1.0,
        diversion_pct=0.5,
        primary_delay_cause="NAS",
    )
    
    service.get_airport_delay_metrics.return_value = metrics
    return service

@pytest.fixture
def provider(mock_service) -> BtsOnTimeBulkProvider:
    return BtsOnTimeBulkProvider(service=mock_service, trailing_months=12)

@pytest.mark.asyncio
async def test_bts_on_time_success(provider: BtsOnTimeBulkProvider):
    outcome = await provider.fetch(["BOS"])
    
    assert not outcome.failures
    assert "BOS" in outcome.fields
    
    bos = outcome.fields["BOS"]
    assert "delayed_flights_pct" in bos
    assert "average_delay_minutes" in bos
    
    assert bos["delayed_flights_pct"].value == 17.5
    assert bos["average_delay_minutes"].value == 13.75
    
    assert bos["delayed_flights_pct"].origin.source == "BTS Reporting Carrier On-Time Performance"
    assert bos["delayed_flights_pct"].origin.period == "2025-07 to 2026-06"

@pytest.mark.asyncio
async def test_bts_on_time_unloaded(provider: BtsOnTimeBulkProvider, mock_service):
    mock_service.is_loaded = False
    
    outcome = await provider.fetch(["BOS"])
    
    assert not outcome.fields
    assert len(outcome.failures) == 1
    assert outcome.failures[0].provider == "BTS_OTP_BULK"

@pytest.mark.asyncio
async def test_bts_on_time_missing_airport(provider: BtsOnTimeBulkProvider, mock_service):
    mock_service.get_airport_delay_metrics.return_value = None
    
    outcome = await provider.fetch(["BOS"])
    
    assert not outcome.fields
    assert len(outcome.failures) == 1
    assert "No departure delay data for BOS" in outcome.failures[0].error
