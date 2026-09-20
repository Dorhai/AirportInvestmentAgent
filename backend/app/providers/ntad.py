from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx

from app.models.airport import IATA, Airport, normalize_iata
from app.models.context import FacilityContext
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome

logger = logging.getLogger(__name__)

class NtadFacilitiesProvider:
    _URL = "https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Aviation_Facilities/FeatureServer/0/query"

    def __init__(self, http: httpx.AsyncClient, timeout_s: float) -> None:
        self._http = http
        self._timeout = timeout_s

    @property
    def name(self) -> str:
        return "NTAD_Facilities"

    async def fetch_facilities(self, codes: Sequence[IATA]) -> tuple[dict[str, Airport], dict[str, FacilityContext], list[ProviderFailure]]:
        airports: dict[str, Airport] = {}
        facilities: dict[str, FacilityContext] = {}
        failures: list[ProviderFailure] = []

        if not codes:
            return airports, facilities, failures

        try:
            normalized = [normalize_iata(c) for c in codes]
        except ValueError as exc:
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            return airports, facilities, failures

        requested = set(normalized)
        id_str = ",".join(f"'{c}'" for c in normalized)

        query = {
            "where": f"ARPT_ID IN ({id_str})",
            "outFields": "ARPT_ID,ICAO_ID,ARPT_NAME,CITY,STATE_CODE,LAT_DECIMAL,LONG_DECIMAL,ACREAGE,FAR_139_TYPE_CODE,TWR_TYPE_CODE,ARPT_STATUS,EFF_DATE",
            "f": "json",
            "returnGeometry": "false",
        }

        try:
            resp = await self._http.get(self._URL, params=query, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                failures.append(ProviderFailure(provider=self.name, error=data["error"].get("message", "Unknown ArcGIS error")))
                return airports, facilities, failures

        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("NTAD Facilities request failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            return airports, facilities, failures

        features = data.get("features", [])

        for feature in features:
            attrs = feature.get("attributes", {})
            arpt_id = attrs.get("ARPT_ID")
            if not arpt_id:
                continue
            iata = normalize_iata(str(arpt_id))
            if iata not in requested:
                continue

            icao = str(attrs.get("ICAO_ID") or "")

            try:
                airports[iata] = Airport(
                    iata_code=iata,
                    icao_code=icao,
                    name=attrs.get("ARPT_NAME", "") or iata,
                    city=attrs.get("CITY", "") or "",
                    state=attrs.get("STATE_CODE", "") or "",
                    latitude=float(attrs.get("LAT_DECIMAL", 0.0) or 0.0),
                    longitude=float(attrs.get("LONG_DECIMAL", 0.0) or 0.0),
                )

                facilities[iata] = FacilityContext(
                    acreage=int(attrs["ACREAGE"]) if attrs.get("ACREAGE") is not None else None,
                    part139_class=attrs.get("FAR_139_TYPE_CODE"),
                    tower_type=attrs.get("TWR_TYPE_CODE"),
                    status=attrs.get("ARPT_STATUS"),
                    effective_date=str(attrs.get("EFF_DATE", "")),
                    source="NTAD Aviation Facilities",
                )
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse NTAD feature for %s: %s", iata, e)

        return airports, facilities, failures

    async def fetch_codes_by_states(self, states: Sequence[str]) -> tuple[list[str], list[ProviderFailure]]:
        codes: set[str] = set()
        failures: list[ProviderFailure] = []

        if not states:
            return [], failures

        states_str = ",".join(f"'{s}'" for s in states)
        query = {
            "where": f"STATE_CODE IN ({states_str}) AND FAR_139_TYPE_CODE IS NOT NULL AND FAR_139_TYPE_CODE <> ''",
            "outFields": "ARPT_ID",
            "f": "json",
            "returnGeometry": "false",
        }

        try:
            resp = await self._http.get(self._URL, params=query, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                failures.append(ProviderFailure(provider=self.name, error=data["error"].get("message", "Unknown ArcGIS error")))
                return [], failures

        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("NTAD Facilities states request failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            return [], failures

        features = data.get("features", [])
        for feature in features:
            attrs = feature.get("attributes", {})
            arpt_id = attrs.get("ARPT_ID")
            if not arpt_id:
                continue
            try:
                iata = normalize_iata(str(arpt_id))
                codes.add(iata)
            except ValueError:
                # Skip IDs that are not valid 3-letter IATA codes (e.g. 01A)
                pass

        return sorted(codes), failures

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        _, facilities, failures = await self.fetch_facilities(codes)

        contexts: dict[str, dict[str, FacilityContext]] = {}
        for code, facility in facilities.items():
            contexts[code] = {"facility": facility}

        return ContextOutcome(fields=contexts, failures=failures, warnings={})
