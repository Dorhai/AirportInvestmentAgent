import pytest
import httpx
from datetime import date

from app.providers.bts_t100_origin import BtsT100OriginProvider
from app.models.metrics import Live, Proxy

@pytest.mark.asyncio
async def test_bts_t100_origin_provider(respx_mock):
    respx_mock.get("https://data.bts.gov/resource/r495-tyji.json").respond(
        json=[
            {
                "origin_airport_code": "BOS",
                "reporting_month": "2026-04-01T00:00:00.000",
                "total_departures": "1000",
                "total_passengers": "10000",
                "total_seats": "12000",
                "outbound_international": "100",
                "total_distance_flight_sm": "1000.0"
            },
            {
                "origin_airport_code": "BOS",
                "reporting_month": "2026-03-01T00:00:00.000",
                "total_departures": "1000",
                "total_passengers": "10000",
                "total_seats": "12000",
                "outbound_international": "100",
                "total_distance_flight_sm": "1000.0"
            },
            {
                "origin_airport_code": "BOS",
                "reporting_month": "2026-02-01T00:00:00.000",
                "total_departures": "900",
                "total_passengers": "9000",
                "total_seats": "11000",
                "outbound_international": "90",
                "total_distance_flight_sm": "900.0"
            },
            {
                "origin_airport_code": "BOS",
                "reporting_month": "2026-01-01T00:00:00.000",
                "total_departures": "900",
                "total_passengers": "9000",
                "total_seats": "11000",
                "outbound_international": "90",
                "total_distance_flight_sm": "900.0"
            }
        ]
    )

    async with httpx.AsyncClient() as client:
        provider = BtsT100OriginProvider(client, timeout_s=1.0, trailing_months=2)
        outcome = await provider.fetch(["BOS", "JFK"])

    assert not outcome.failures
    assert "JFK" in outcome.warnings
    assert "incomplete 2-month trailing window" in outcome.warnings["JFK"][0]
    
    assert "BOS" in outcome.fields
    bos = outcome.fields["BOS"]
    
    assert bos["passenger_volume"].value == 20000
    assert isinstance(bos["passenger_volume"].origin, Live)
    assert bos["passenger_volume"].origin.source == "BTS T-100 Segment Summary by Origin"
    
    assert bos["previous_passenger_volume"].value == 18000
    
    assert bos["total_departures"].value == 2000
    assert bos["international_departures"].value == 200
    assert bos["average_flight_distance_sm"].value == 1000.0
    
    assert bos["annual_operations"].value == 2000
    assert isinstance(bos["annual_operations"].origin, Proxy)
    assert bos["annual_operations"].origin.method == "annual_operations_from_t100_departures"

@pytest.mark.asyncio
async def test_bts_t100_origin_provider_http_error(respx_mock):
    respx_mock.get("https://data.bts.gov/resource/r495-tyji.json").respond(status_code=500)

    async with httpx.AsyncClient() as client:
        provider = BtsT100OriginProvider(client, timeout_s=1.0)
        outcome = await provider.fetch(["BOS"])

    assert len(outcome.failures) == 1
    assert outcome.failures[0].provider == "BTS_T100_ORIGIN"
    assert not outcome.fields
