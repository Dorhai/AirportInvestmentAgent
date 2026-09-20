import pytest
import httpx

from app.providers.bts_national import BtsNationalTrafficProvider
from app.models.context import NationalTrafficContext

@pytest.mark.asyncio
async def test_bts_national_provider(respx_mock):
    respx_mock.get("https://data.bts.gov/resource/jqx4-4iha.json").respond(
        json=[
            {
                "date": "2026-04-01T00:00:00.000",
                "departures": "1000",
                "passengers": "10000",
                "seats": "12000"
            },
            {
                "date": "2026-03-01T00:00:00.000",
                "departures": "1000",
                "passengers": "10000",
                "seats": "12000"
            },
            {
                "date": "2026-02-01T00:00:00.000",
                "departures": "900",
                "passengers": "9000",
                "seats": "11000"
            },
            {
                "date": "2026-01-01T00:00:00.000",
                "departures": "900",
                "passengers": "9000",
                "seats": "11000"
            }
        ]
    )

    async with httpx.AsyncClient() as client:
        provider = BtsNationalTrafficProvider(client, timeout_s=1.0, trailing_months=2)
        outcome = await provider.fetch(["BOS", "JFK"])

    assert not outcome.failures
    assert "BOS" in outcome.fields
    assert "JFK" in outcome.fields
    
    bos_ctx = outcome.fields["BOS"]["national_traffic"]
    assert isinstance(bos_ctx, NationalTrafficContext)
    assert bos_ctx.passengers_12m == 20000
    assert bos_ctx.passengers_prev_12m == 18000
    assert bos_ctx.departures_12m == 2000
    assert bos_ctx.growth_pct > 0
    assert bos_ctx.load_factor_pct > 0
    
    # Check that national rows never appear as any airport's passenger_volume
    # (they are only in contexts)
    assert "passenger_volume" not in outcome.fields["BOS"]

@pytest.mark.asyncio
async def test_bts_national_provider_http_error(respx_mock):
    respx_mock.get("https://data.bts.gov/resource/jqx4-4iha.json").respond(status_code=500)

    async with httpx.AsyncClient() as client:
        provider = BtsNationalTrafficProvider(client, timeout_s=1.0)
        outcome = await provider.fetch(["BOS"])

    assert len(outcome.failures) == 1
    assert outcome.failures[0].provider == "BTS_National_Traffic"
    assert not outcome.fields
