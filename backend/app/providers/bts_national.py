from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

import httpx

from app.analytics.t100 import MonthlyTraffic, trailing_windows
from app.models.airport import IATA
from app.models.context import NationalTrafficContext
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome

logger = logging.getLogger(__name__)

class BtsNationalTrafficProvider:
    _URL = "https://data.bts.gov/resource/jqx4-4iha.json"

    def __init__(
        self,
        http: httpx.AsyncClient,
        timeout_s: float,
        app_token: str | None = None,
        trailing_months: int = 12,
    ) -> None:
        self._http = http
        self._timeout = timeout_s
        self._app_token = app_token
        self._trailing_months = trailing_months

    @property
    def name(self) -> str:
        return "BTS_National_Traffic"

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        contexts: dict[str, dict[str, NationalTrafficContext]] = {}
        failures: list[ProviderFailure] = []
        warnings: dict[str, list[str]] = {}

        if not codes:
            return ContextOutcome(fields=contexts, failures=failures, warnings=warnings)

        limit = self._trailing_months * 2 + 3
        
        query = {
            "$select": "date,departures,passengers,seats",
            "$order": "date DESC",
            "$limit": limit,
        }
        
        headers = {}
        if self._app_token:
            headers["X-App-Token"] = self._app_token

        try:
            resp = await self._http.get(self._URL, params=query, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("BTS National Traffic request failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            return ContextOutcome(fields=contexts, failures=failures, warnings=warnings)

        rows: list[MonthlyTraffic] = []
        for row in data:
            try:
                dt = datetime.fromisoformat(row["date"].replace("Z", "+00:00")).date()
                rows.append(MonthlyTraffic(
                    code="US",
                    month=dt,
                    departures=int(row.get("departures", 0)),
                    passengers=int(row.get("passengers", 0)),
                    seats=int(row.get("seats", 0)),
                    intl_departures=0,
                ))
            except (ValueError, KeyError) as e:
                logger.warning("Failed to parse BTS National Traffic row: %s", e)
                continue

        windows = trailing_windows(rows, months=self._trailing_months)
        
        if "US" not in windows:
            # We don't have enough data
            failure = ProviderFailure(provider=self.name, error=f"Incomplete {self._trailing_months}-month trailing window for national data")
            failures.append(failure)
            return ContextOutcome(fields=contexts, failures=failures, warnings=warnings)
            
        comp = windows["US"]
        
        growth_pct = 0.0
        if comp.previous.passengers > 0:
            growth_pct = ((comp.current.passengers - comp.previous.passengers) / comp.previous.passengers) * 100.0
            
        load_factor_pct = 0.0
        if comp.current.seats > 0:
            load_factor_pct = (comp.current.passengers / comp.current.seats) * 100.0
            
        ctx = NationalTrafficContext(
            period=comp.period_label,
            passengers_12m=comp.current.passengers,
            passengers_prev_12m=comp.previous.passengers,
            growth_pct=growth_pct,
            departures_12m=comp.current.departures,
            load_factor_pct=load_factor_pct,
            source="BTS AFF T-100 Summary"
        )
        
        for code in codes:
            contexts[code] = {"national_traffic": ctx}

        return ContextOutcome(fields=contexts, failures=failures, warnings=warnings)
