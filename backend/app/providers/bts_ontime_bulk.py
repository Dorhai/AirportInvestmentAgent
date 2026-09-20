from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from dateutil.relativedelta import relativedelta

from app.models.airport import IATA
from app.models.metrics import Live, Present
from app.models.score import ProviderFailure
from app.providers.base import ProviderOutcome
from app.services.bts_ontime_service import BtsOnTimeService

logger = logging.getLogger(__name__)

class BtsOnTimeBulkProvider:
    def __init__(self, service: BtsOnTimeService, trailing_months: int = 12) -> None:
        self._service = service
        self._trailing_months = trailing_months

    @property
    def name(self) -> str:
        return "BTS_OTP_BULK"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []
        warnings: dict[str, list[str]] = {}

        if not self._service.is_loaded:
            failures.append(ProviderFailure(provider=self.name, error="BTS On-Time service is not loaded"))
            return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

        max_date = self._service.data_max_date
        if not max_date:
            failures.append(ProviderFailure(provider=self.name, error="BTS On-Time service has no data"))
            return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)

        # Calculate trailing window
        # e.g. if max_date is 2026-06-30, start_date is 2025-07-01
        start_date = (max_date.replace(day=1) - relativedelta(months=self._trailing_months - 1))
        
        fetched_at = self._service.loaded_at or ""

        for code in codes:
            metrics = self._service.get_airport_delay_metrics(
                code,
                start_date=start_date,
                end_date=max_date,
                direction="departures"
            )
            
            if not metrics or metrics.departure_delay_pct is None or metrics.average_departure_delay_minutes is None:
                failures.append(ProviderFailure(provider=self.name, error=f"No departure delay data for {code} in trailing window"))
                continue
                
            origin = Live(
                source="BTS Reporting Carrier On-Time Performance",
                period=metrics.period,
                fetched_at=fetched_at
            )
            
            fields[code] = {
                "delayed_flights_pct": Present[float](value=metrics.departure_delay_pct, origin=origin),
                "average_delay_minutes": Present[float](value=metrics.average_departure_delay_minutes, origin=origin),
            }

        return ProviderOutcome(fields=fields, failures=failures, warnings=warnings)
