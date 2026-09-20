import pytest
import httpx

from app.providers.ntad import NtadFacilitiesProvider
from app.models.context import FacilityContext
from app.models.airport import Airport

@pytest.mark.asyncio
async def test_ntad_provider(respx_mock):
    respx_mock.get("https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Aviation_Facilities/FeatureServer/0/query").respond(
        json={
            "features": [
                {
                    "attributes": {
                        "ARPT_ID": "BOS",
                        "ICAO_ID": "KBOS",
                        "ARPT_NAME": "General Edward Lawrence Logan Intl",
                        "CITY": "Boston",
                        "STATE_CODE": "MA",
                        "LAT_DECIMAL": 42.36429977,
                        "LONG_DECIMAL": -71.00520325,
                        "ACREAGE": 2384,
                        "FAR_139_TYPE_CODE": "I",
                        "TWR_TYPE_CODE": "ATCT",
                        "ARPT_STATUS": "O",
                        "EFF_DATE": 1699999999000
                    }
                }
            ]
        }
    )

    async with httpx.AsyncClient() as client:
        provider = NtadFacilitiesProvider(client, timeout_s=1.0)
        
        # Test fetch_facilities
        airports, facilities, failures = await provider.fetch_facilities(["BOS", "JFK"])
        
        assert not failures
        assert "BOS" in airports
        assert "BOS" in facilities
        assert "JFK" not in airports
        
        bos_airport = airports["BOS"]
        assert isinstance(bos_airport, Airport)
        assert bos_airport.iata_code == "BOS"
        assert bos_airport.icao_code == "KBOS"
        assert bos_airport.latitude == 42.36429977
        
        bos_facility = facilities["BOS"]
        assert isinstance(bos_facility, FacilityContext)
        assert bos_facility.acreage == 2384
        assert bos_facility.part139_class == "I"
        
        # Test ContextProvider fetch
        outcome = await provider.fetch(["BOS", "JFK"])
        assert not outcome.failures
        assert "BOS" in outcome.fields
        assert "facility" in outcome.fields["BOS"]
        assert outcome.fields["BOS"]["facility"].acreage == 2384

@pytest.mark.asyncio
async def test_ntad_provider_http_error(respx_mock):
    respx_mock.get("https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Aviation_Facilities/FeatureServer/0/query").respond(status_code=500)

    async with httpx.AsyncClient() as client:
        provider = NtadFacilitiesProvider(client, timeout_s=1.0)
        airports, facilities, failures = await provider.fetch_facilities(["BOS"])

    assert len(failures) == 1
    assert failures[0].provider == "NTAD_Facilities"
    assert not airports
    assert not facilities

@pytest.mark.asyncio
async def test_ntad_fetch_codes_by_states(respx_mock):
    respx_mock.get("https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Aviation_Facilities/FeatureServer/0/query").respond(
        json={
            "features": [
                {"attributes": {"ARPT_ID": "BOS"}},
                {"attributes": {"ARPT_ID": "PVD"}},
                {"attributes": {"ARPT_ID": "01A"}},  # Should be skipped (invalid IATA)
                {"attributes": {"ARPT_ID": "BOS"}},  # Duplicate should be handled
                {"attributes": {}},  # Missing ARPT_ID
            ]
        }
    )

    async with httpx.AsyncClient() as client:
        provider = NtadFacilitiesProvider(client, timeout_s=1.0)
        codes, failures = await provider.fetch_codes_by_states(["MA", "RI"])

    assert not failures
    assert codes == ["BOS", "PVD"]

@pytest.mark.asyncio
async def test_ntad_fetch_codes_by_states_empty():
    async with httpx.AsyncClient() as client:
        provider = NtadFacilitiesProvider(client, timeout_s=1.0)
        codes, failures = await provider.fetch_codes_by_states([])

    assert not failures
    assert not codes
