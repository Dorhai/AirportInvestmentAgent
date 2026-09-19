from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel

from app.analytics.long_haul import haversine_miles, is_long_haul
from app.models.airport import IATA
from app.models.context import DelayProgram
from app.models.metrics import Live, Present
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome, ProviderOutcome
from app.providers.opensky_auth import OpenSkyTokenManager

logger = logging.getLogger(__name__)

_DAY_S = 86_400

_OPENSKY_429_MAX_ATTEMPTS = 6


def _opensky_backoff_s(resp: httpx.Response, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass
    return min(60.0, 5.0 * (2**attempt))


class OpenSkyProvider:
    _BASE = "https://opensky-network.org/api/flights/departure"
    _fetch_lock: asyncio.Lock | None = None

    def __init__(
        self,
        http: httpx.AsyncClient,
        coords: Any,  # services.airport_service.CoordinateLookup
        timeout_s: float,
        token_manager: OpenSkyTokenManager | None = None,
        window_days: int = 7,
        request_delay_s: float = 0.5,
    ) -> None:
        self._http = http
        self._coords = coords
        self._timeout = timeout_s
        self._token_manager = token_manager
        self._window_days = window_days
        self._request_delay_s = request_delay_s

    @property
    def name(self) -> str:
        return "OpenSky"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        if OpenSkyProvider._fetch_lock is None:
            OpenSkyProvider._fetch_lock = asyncio.Lock()
        async with OpenSkyProvider._fetch_lock:
            return await self._fetch_locked(codes)

    async def _fetch_locked(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []
        warnings: dict[str, list[str]] = {}

        now = int(time.time())
        end = now - _DAY_S
        begin = end - (self._window_days * _DAY_S)

        for i, code in enumerate(codes):
            if i > 0 and self._request_delay_s > 0:
                await asyncio.sleep(self._request_delay_s)

            icao = self._coords.icao_for(code)
            if icao is None:
                failures.append(
                    ProviderFailure(provider=self.name, error=f"No ICAO mapping for {code}")
                )
                continue

            all_flights: list[dict] = []
            current_begin = begin
            while current_begin < end:
                current_end = min(current_begin + _DAY_S, end)
                day_flights, _meta = await self._fetch_departures(
                    icao, current_begin, current_end
                )
                if day_flights is not None:
                    all_flights.extend(day_flights)
                current_begin += _DAY_S
                if current_begin < end and self._request_delay_s > 0:
                    await asyncio.sleep(self._request_delay_s)

            if not all_flights:
                warnings.setdefault(code, []).append(f"OpenSky: No departure data for {code}")
                continue

            # Dedupe by icao24 + firstSeen
            unique_flights = {}
            for f in all_flights:
                key = (f.get("icao24"), f.get("firstSeen"))
                if key[0] and key[1]:
                    unique_flights[key] = f
            flights = list(unique_flights.values())

            origin_coords = self._coords.get(icao)
            if origin_coords is None:
                failures.append(
                    ProviderFailure(provider=self.name, error=f"No coords for {icao}")
                )
                continue

            raw_total = len(flights)
            resolved = 0
            long_haul = 0
            lat1, lon1 = origin_coords

            for f in flights:
                dest_icao = f.get("estArrivalAirport")
                if not dest_icao:
                    continue
                dest_coords = self._coords.get(dest_icao)
                if dest_coords is None:
                    continue
                resolved += 1
                dist = haversine_miles(lat1, lon1, dest_coords[0], dest_coords[1])
                if is_long_haul(dist):
                    long_haul += 1

            if resolved == 0:
                warnings.setdefault(code, []).append(
                    f"OpenSky: No departures with resolvable destination for {code} ({raw_total} raw departures)"
                )
                continue

            if raw_total > 0 and (resolved / raw_total) < 0.5:
                warnings.setdefault(code, []).append(
                    f"OpenSky: only {resolved}/{raw_total} departures had resolvable destinations."
                )

            logger.info(
                "OpenSky %s: resolved %d/%d departures for long-haul",
                code,
                resolved,
                raw_total,
            )

            period_begin = time.strftime("%Y-%m-%d", time.gmtime(begin))
            period_end = time.strftime("%Y-%m-%d", time.gmtime(end))
            period = f"{period_begin} to {period_end}"
            fetched = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            origin = Live(source="OpenSky Network", period=period, fetched_at=fetched)

            fields[code] = {
                "total_departures": Present[int](value=resolved, origin=origin),
                "long_haul_flights": Present[int](value=long_haul, origin=origin),
            }

        return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

    async def _fetch_departures(
        self, icao: str, begin: int, end: int
    ) -> tuple[list[dict] | None, dict[str, int]]:
        params = {"airport": icao, "begin": str(begin), "end": str(end)}
        meta: dict[str, int] = {"http_calls": 0, "status_429": 0}

        for attempt in range(_OPENSKY_429_MAX_ATTEMPTS):
            headers: dict[str, str] = {}
            if self._token_manager is not None:
                headers = await self._token_manager.bearer_headers()

            try:
                resp = await self._http.get(
                    self._BASE,
                    params=params,
                    timeout=self._timeout,
                    headers=headers,
                )
                meta["http_calls"] += 1
                if resp.status_code == 404:
                    return None, meta
                if resp.status_code == 401 and self._token_manager is not None:
                    self._token_manager.invalidate()
                    if attempt == 0:
                        logger.warning("OpenSky 401 for %s, refreshing token", icao)
                        continue
                    return None, meta
                if resp.status_code == 400:
                    logger.warning(
                        "OpenSky 400 for %s (span %sh): %s",
                        icao,
                        round((end - begin) / 3600, 1),
                        (resp.text or "")[:200],
                    )
                    return None, meta
                if resp.status_code == 429:
                    meta["status_429"] += 1
                    backoff = _opensky_backoff_s(resp, attempt)
                    if attempt < _OPENSKY_429_MAX_ATTEMPTS - 1:
                        logger.warning(
                            "OpenSky 429 for %s, sleeping %.1fs (attempt %d)",
                            icao,
                            backoff,
                            attempt + 1,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    logger.warning("OpenSky HTTP error for %s: 429", icao)
                    return None, meta
                resp.raise_for_status()
                return resp.json(), meta  # type: ignore[return-value]
            except httpx.TransportError:
                if attempt < _OPENSKY_429_MAX_ATTEMPTS - 1:
                    logger.warning("OpenSky transport error for %s, retrying", icao)
                    await asyncio.sleep(min(10.0, 2.0 * (attempt + 1)))
                    continue
                return None, meta
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.warning("OpenSky HTTP error for %s: %s", icao, status)
                return None, meta
        return None, meta


class FaaNasProvider:
    _URL = "https://nasstatus.faa.gov/api/airport-status-information"

    def __init__(self, http: httpx.AsyncClient, timeout_s: float) -> None:
        self._http = http
        self._timeout = timeout_s

    @property
    def name(self) -> str:
        return "FAA_NAS"

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        fields: dict[str, dict[str, Any]] = {}
        failures: list[ProviderFailure] = []

        programs = await self._fetch_programs()
        if programs is None:
            failures.append(
                ProviderFailure(provider=self.name, error="Failed to fetch NAS status")
            )
            return ContextOutcome(fields=fields, failures=failures)

        for code in codes:
            matching = [p for p in programs if p.airport_icao.endswith(code)]
            if matching:
                fields[code] = {
                    "nas_delay_program": matching[0],
                }

        return ContextOutcome(fields=fields, failures=failures)

    async def _fetch_programs(self) -> list[DelayProgram] | None:
        try:
            resp = await self._http.get(self._URL, timeout=self._timeout)
            resp.raise_for_status()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("FAA NAS request failed: %s", exc)
            return None

        return self._parse_xml(resp.text)

    @staticmethod
    def _parse_xml(xml_text: str) -> list[DelayProgram]:
        programs: list[DelayProgram] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse FAA NAS XML")
            return programs

        for delay_el in root.iter("Delay"):
            arpt = delay_el.findtext("ARPT", "")
            program = delay_el.findtext("Reason", "")
            reason = delay_el.findtext("Type", "")
            avg_delay = delay_el.findtext("Avg", "")
            updated = delay_el.findtext("Updated", "")

            if arpt:
                programs.append(
                    DelayProgram(
                        airport_icao=arpt,
                        program=program,
                        reason=reason,
                        avg_delay=avg_delay,
                        updated_at=updated,
                    )
                )
        return programs
