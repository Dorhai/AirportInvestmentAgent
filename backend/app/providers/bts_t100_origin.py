from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

import httpx

from app.analytics.t100 import MonthlyTraffic, trailing_windows
from app.models.airport import IATA
from app.models.metrics import Live, Present, Proxy, Derived
from app.models.score import ProviderFailure
from app.providers.base import ProviderOutcome

logger = logging.getLogger(__name__)

class BtsT100OriginProvider:
    _URL = "https://data.bts.gov/resource/r495-tyji.json"

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
        return "BTS_T100_ORIGIN"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []
        warnings: dict[str, list[str]] = {}

        if not codes:
            return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

        # We need data for the current window and the previous window.
        # So we need at least 2 * trailing_months months of data.
        # Let's fetch 2 * trailing_months + 3 to be safe and ensure we have enough.
        limit = len(codes) * (self._trailing_months * 2 + 3)
        codes_str = ",".join(f"'{c}'" for c in codes)
        
        query = {
            "$select": "origin_airport_code,reporting_month,total_departures,total_passengers,total_seats,outbound_international,total_distance_flight_sm",
            "$where": f"origin_airport_code in({codes_str})",
            "$order": "reporting_month DESC",
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
            logger.warning("BTS T100 Origin request failed: %s", exc)
            failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

        rows: list[MonthlyTraffic] = []
        for row in data:
            try:
                # reporting_month is like "2026-04-01T00:00:00.000"
                dt = datetime.fromisoformat(row["reporting_month"].replace("Z", "+00:00")).date()
                
                dist_str = row.get("total_distance_flight_sm")
                avg_dist = float(dist_str) if dist_str is not None else None
                
                rows.append(MonthlyTraffic(
                    code=row["origin_airport_code"],
                    month=dt,
                    departures=int(row.get("total_departures", 0)),
                    passengers=int(row.get("total_passengers", 0)),
                    seats=int(row.get("total_seats", 0)),
                    intl_departures=int(row.get("outbound_international", 0)),
                    avg_distance_sm=avg_dist
                ))
            except (ValueError, KeyError) as e:
                logger.warning("Failed to parse BTS T100 Origin row: %s", e)
                continue

        windows = trailing_windows(rows, months=self._trailing_months)
        
        fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        for code in codes:
            if code not in windows:
                warnings.setdefault(code, []).append(f"BTS T-100: incomplete {self._trailing_months}-month trailing window")
                continue
                
            comp = windows[code]
            
            origin = Live(
                source="BTS T-100 Segment Summary by Origin",
                period=comp.period_label,
                fetched_at=fetched_at
            )
            
            airport_fields: dict[str, Present] = {
                "passenger_volume": Present[int](value=comp.current.passengers, origin=origin),
                "previous_passenger_volume": Present[int](value=comp.previous.passengers, origin=origin),
                "total_departures": Present[int](value=comp.current.departures, origin=origin),
                "international_departures": Present[int](value=comp.current.intl_departures, origin=origin),
            }
            
            if comp.current.avg_distance_sm is not None:
                dist_origin = Derived(
                    method="departure_weighted_mean_stage_length",
                    inputs=("live",),
                    period=comp.period_label,
                    sources=("BTS T-100 Segment Summary by Origin",),
                    freshness="live"
                )
                airport_fields["average_flight_distance_sm"] = Present[float](value=comp.current.avg_distance_sm, origin=dist_origin)
            
            ops_origin = Proxy(
                method="annual_operations_from_t100_departures",
                inputs=("live",),
                assumption="Commercial performed departures reported to BTS, not total FAA tower operations",
                period=comp.period_label,
                sources=("BTS T-100 Segment Summary by Origin",),
                freshness="live"
            )
            airport_fields["annual_operations"] = Present[int](value=comp.current.departures, origin=ops_origin)
            
            fields[code] = airport_fields

        return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)
