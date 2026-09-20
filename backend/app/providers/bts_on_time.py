from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

import httpx

from app.analytics.t100 import MonthlyTraffic, trailing_windows
from app.models.airport import IATA
from app.models.metrics import Live, Present
from app.models.score import ProviderFailure
from app.providers.base import ProviderOutcome

logger = logging.getLogger(__name__)

class BtsOnTimeProvider:
    # Hypothetical Socrata endpoint for BTS On-Time Performance.
    # The actual BTS open-data catalog currently lacks a tabular Socrata dataset for this,
    # so this serves as a structural implementation that will gracefully fail and return Absent.
    _URL = "https://data.bts.gov/resource/284a-79t5.json"

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
        return "BTS_OTP"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []
        warnings: dict[str, list[str]] = {}

        if not codes:
            return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

        # We need data for the current window.
        limit = len(codes) * (self._trailing_months + 3)
        codes_str = ",".join(f"'{c}'" for c in codes)
        
        # Plausible SoQL query for flight delay data
        query = {
            "$select": "origin,year,month,sum(dep_del15) as delayed_flights,count(*) as total_flights,avg(dep_delay) as avg_delay",
            "$where": f"origin in({codes_str})",
            "$group": "origin,year,month",
            "$order": "year DESC, month DESC",
            "$limit": limit
        }
        
        headers = {}
        if self._app_token:
            headers["X-App-Token"] = self._app_token

        try:
            resp = await self._http.get(self._URL, params=query, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("BTS OTP request failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

        # Process the data
        # We'll group by airport and calculate the trailing window aggregate
        airport_data: dict[str, list[dict]] = {code: [] for code in codes}
        
        for row in data:
            try:
                origin = row["origin"]
                if origin in airport_data:
                    airport_data[origin].append(row)
            except KeyError:
                continue
                
        fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        for code in codes:
            rows = airport_data.get(code, [])
            if not rows:
                failures.append(ProviderFailure(provider=self.name, error=f"No BTS OTP data for {code}"))
                continue
                
            # Take up to trailing_months
            recent_rows = rows[:self._trailing_months]
            
            if len(recent_rows) < self._trailing_months:
                warnings.setdefault(code, []).append(f"BTS OTP: incomplete {self._trailing_months}-month trailing window")
            
            try:
                total_delayed = sum(float(r.get("delayed_flights", 0)) for r in recent_rows)
                total_flights = sum(float(r.get("total_flights", 0)) for r in recent_rows)
                
                # Weighted average for avg_delay
                total_delay_minutes = sum(float(r.get("avg_delay", 0)) * float(r.get("total_flights", 0)) for r in recent_rows)
                
                if total_flights > 0:
                    delayed_pct = (total_delayed / total_flights) * 100.0
                    avg_delay = total_delay_minutes / total_flights
                else:
                    delayed_pct = 0.0
                    avg_delay = 0.0
                    
                period_label = f"Last {len(recent_rows)} months"
                
                origin_meta = Live(
                    source="BTS On-Time Performance",
                    period=period_label,
                    fetched_at=fetched_at
                )
                
                fields[code] = {
                    "delayed_flights_pct": Present[float](value=delayed_pct, origin=origin_meta),
                    "average_delay_minutes": Present[float](value=avg_delay, origin=origin_meta),
                }
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse BTS OTP data for %s: %s", code, e)
                failures.append(ProviderFailure(provider=self.name, error=f"Parse error: {e}"))

        return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)
