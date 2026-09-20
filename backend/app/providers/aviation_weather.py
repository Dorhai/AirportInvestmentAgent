from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol

import httpx

from app.models.airport import IATA
from app.models.context import WeatherContext
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome

logger = logging.getLogger(__name__)


class _IcaoLookup(Protocol):
    def get(self, code: str) -> Any | None: ...


class AviationWeatherProvider:
    _URL = "https://aviationweather.gov/api/data/metar"

    def __init__(
        self,
        http: httpx.AsyncClient,
        timeout_s: float,
        catalog: _IcaoLookup,
    ) -> None:
        self._http = http
        self._timeout = timeout_s
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "AviationWeather"

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        contexts: dict[str, dict[str, Any]] = {}
        failures: list[ProviderFailure] = []

        if not codes:
            return ContextOutcome(fields=contexts, failures=failures, warnings={})

        code_to_icao: dict[str, str] = {}
        for code in codes:
            airport = self._catalog.get(code)
            if airport and airport.icao_code:
                code_to_icao[code] = airport.icao_code

        if not code_to_icao:
            return ContextOutcome(fields=contexts, failures=failures, warnings={})

        icao_str = ",".join(code_to_icao.values())

        try:
            resp = await self._http.get(
                self._URL,
                params={"ids": icao_str, "format": "json"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                failures.append(ProviderFailure(provider=self.name, error="Unexpected response format"))
                return ContextOutcome(fields=contexts, failures=failures, warnings={})

            icao_to_iata = {v: k for k, v in code_to_icao.items()}

            metars_by_icao: dict[str, dict[str, Any]] = {}
            for metar in data:
                icao_id = metar.get("icaoId")
                if icao_id and icao_id not in metars_by_icao:
                    metars_by_icao[icao_id] = metar

            for code, icao in code_to_icao.items():
                metar = metars_by_icao.get(icao)
                if not metar:
                    failures.append(
                        ProviderFailure(provider=self.name, error=f"No weather data for {code}")
                    )
                    continue

                flight_category = metar.get("fltcat", "Unknown")
                wind_dir = metar.get("wdir", "VRB")
                wind_spd = metar.get("wspd", 0)
                wind = f"{wind_dir} at {wind_spd} kt"
                vis = str(metar.get("visib", "Unknown"))
                obs_time = str(metar.get("obsTime", "Unknown"))
                raw_ob = metar.get("rawOb", "")

                contexts[code] = {
                    "weather": WeatherContext(
                        flight_category=flight_category,
                        wind=wind,
                        visibility=vis,
                        remarks=raw_ob,
                        observation_time=obs_time,
                    )
                }

        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("Weather request failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
        except (ValueError, KeyError, IndexError) as exc:
            logger.warning("Weather parse failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=f"Parse error: {exc}"))

        return ContextOutcome(fields=contexts, failures=failures, warnings={})
