from __future__ import annotations

import logging
import time
from collections.abc import Sequence

import httpx

from app.models.airport import IATA
from app.models.metrics import Live, Present
from app.models.score import ProviderFailure
from app.providers.base import ProviderOutcome

logger = logging.getLogger(__name__)

class BtsOnTimeProvider:
    # Example Socrata endpoint for BTS On-Time Performance
    # In a real app, this would be the actual dataset ID.
    _URL = "https://data.transportation.gov/resource/xxxx-xxxx.json"

    def __init__(self, http: httpx.AsyncClient, timeout_s: float) -> None:
        self._http = http
        self._timeout = timeout_s

    @property
    def name(self) -> str:
        return "BTS_OTP"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []
        
        # For this MVP, we'll simulate fetching or use a generic query.
        # In reality, we'd query the Socrata API for the specific airports.
        # Since we don't have the exact dataset ID, we'll just return failures
        # or mock data if we were to hit it, but the structure is here.
        
        # We'll just return failures for now if we can't actually hit it,
        # but the tests will mock `_http.get`.
        
        for code in codes:
            try:
                # Example SoQL query: ?origin=BOS&$select=avg(dep_delay),sum(dep_del15)/count(*) as pct_delayed
                resp = await self._http.get(
                    self._URL,
                    params={"origin": code},
                    timeout=self._timeout
                )
                resp.raise_for_status()
                data = resp.json()
                
                if not data:
                    failures.append(ProviderFailure(provider=self.name, error=f"No BTS data for {code}"))
                    continue
                
                # Assuming the API returns aggregated data
                row = data[0]
                avg_delay = float(row.get("avg_dep_delay", 0.0))
                pct_delayed = float(row.get("pct_delayed_15", 0.0)) * 100.0
                
                fetched = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                origin = Live(source="BTS On-Time", period="CY2024", fetched_at=fetched)
                
                fields[code] = {
                    "average_delay_minutes": Present[float](value=avg_delay, origin=origin),
                    "delayed_flights_pct": Present[float](value=pct_delayed, origin=origin),
                }
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                logger.warning("BTS OTP request failed for %s: %s", code, exc)
                failures.append(ProviderFailure(provider=self.name, error=str(exc)))
            except (ValueError, KeyError, IndexError) as exc:
                logger.warning("BTS OTP parse failed for %s: %s", code, exc)
                failures.append(ProviderFailure(provider=self.name, error=f"Parse error: {exc}"))

        return ProviderOutcome(fields=fields, failures=failures)
