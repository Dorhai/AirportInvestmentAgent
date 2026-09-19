from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import httpx

from app.models.airport import IATA
from app.models.context import WeatherContext
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome

logger = logging.getLogger(__name__)


class AviationWeatherProvider:
    # NOAA Aviation Weather Center Data API
    _URL = "https://aviationweather.gov/api/data/metar"

    def __init__(
        self,
        http: httpx.AsyncClient,
        coords: Any,  # services.airport_service.CoordinateLookup
        timeout_s: float,
    ) -> None:
        self._http = http
        self._coords = coords
        self._timeout = timeout_s

    @property
    def name(self) -> str:
        return "AviationWeather"

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        fields: dict[str, dict[str, Any]] = {}
        failures: list[ProviderFailure] = []

        for code in codes:
            icao = self._coords.icao_for(code)
            if not icao:
                failures.append(
                    ProviderFailure(provider=self.name, error=f"No ICAO mapping for {code}")
                )
                continue

            try:
                resp = await self._http.get(
                    self._URL,
                    params={"ids": icao, "format": "json"},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                if not data:
                    failures.append(
                        ProviderFailure(provider=self.name, error=f"No weather data for {code}")
                    )
                    continue

                # The API returns a list of METARs, usually the latest first
                metar = data[0]
                
                flight_category = metar.get("fltcat", "Unknown")
                wind_dir = metar.get("wdir", "VRB")
                wind_spd = metar.get("wspd", 0)
                wind = f"{wind_dir} at {wind_spd} kt"
                vis = str(metar.get("visib", "Unknown"))
                obs_time = str(metar.get("obsTime", "Unknown"))
                raw_ob = metar.get("rawOb", "")

                fields[code] = {
                    "weather": WeatherContext(
                        flight_category=flight_category,
                        wind=wind,
                        visibility=vis,
                        remarks=raw_ob,
                        observation_time=obs_time,
                    )
                }

            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                logger.warning("Weather request failed for %s: %s", code, exc)
                failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            except (ValueError, KeyError, IndexError) as exc:
                logger.warning("Weather parse failed for %s: %s", code, exc)
                failures.append(ProviderFailure(provider=self.name, error=f"Parse error: {exc}"))

        return ContextOutcome(fields=fields, failures=failures)
