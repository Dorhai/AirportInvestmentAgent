import pytest
import httpx

from app.models.airport import Airport
from app.providers.aviation_weather import AviationWeatherProvider
from app.models.context import WeatherContext


class _StubCatalog:
    def __init__(self) -> None:
        self._airports = {
            "BOS": Airport(
                iata_code="BOS",
                icao_code="KBOS",
                name="Boston",
                city="Boston",
                state="MA",
                latitude=0.0,
                longitude=0.0,
            ),
            "JFK": Airport(
                iata_code="JFK",
                icao_code="KJFK",
                name="JFK",
                city="New York",
                state="NY",
                latitude=0.0,
                longitude=0.0,
            ),
        }

    def get(self, code: str) -> Airport | None:
        return self._airports.get(code)


@pytest.mark.asyncio
async def test_aviation_weather_provider(respx_mock):
    respx_mock.get("https://aviationweather.gov/api/data/metar?ids=KBOS,KJFK&format=json").respond(
        json=[
            {
                "icaoId": "KBOS",
                "fltcat": "VFR",
                "wdir": 270,
                "wspd": 10,
                "visib": 10,
                "obsTime": "2026-09-20T12:00:00Z",
                "rawOb": "KBOS 201200Z 27010KT 10SM CLR 15/05 A2992"
            },
            {
                "icaoId": "KJFK",
                "fltcat": "MVFR",
                "wdir": 180,
                "wspd": 15,
                "visib": 5,
                "obsTime": "2026-09-20T12:00:00Z",
                "rawOb": "KJFK 201200Z 18015KT 5SM BR BKN020 18/12 A2980"
            }
        ]
    )

    async with httpx.AsyncClient() as client:
        provider = AviationWeatherProvider(client, timeout_s=1.0, catalog=_StubCatalog())
        outcome = await provider.fetch(["BOS", "JFK"])

    assert not outcome.failures
    assert "BOS" in outcome.fields
    assert "JFK" in outcome.fields

    bos_ctx = outcome.fields["BOS"]["weather"]
    assert isinstance(bos_ctx, WeatherContext)
    assert bos_ctx.flight_category == "VFR"
    assert bos_ctx.wind == "270 at 10 kt"

    jfk_ctx = outcome.fields["JFK"]["weather"]
    assert isinstance(jfk_ctx, WeatherContext)
    assert jfk_ctx.flight_category == "MVFR"
    assert jfk_ctx.visibility == "5"

@pytest.mark.asyncio
async def test_aviation_weather_provider_http_error(respx_mock):
    respx_mock.get("https://aviationweather.gov/api/data/metar?ids=KBOS&format=json").respond(status_code=500)

    catalog = _StubCatalog()
    async with httpx.AsyncClient() as client:
        provider = AviationWeatherProvider(client, timeout_s=1.0, catalog=catalog)
        outcome = await provider.fetch(["BOS"])

    assert len(outcome.failures) == 1
    assert outcome.failures[0].provider == "AviationWeather"
    assert not outcome.fields
