from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from app.core.config import settings
from app.models.airport import IATA, REGIONS, Airport, normalize_iata
from app.models.score import ProviderFailure
from app.providers.ntad import NtadFacilitiesProvider

logger = logging.getLogger(__name__)

class AirportCatalog:
    def __init__(self, source: NtadFacilitiesProvider) -> None:
        self._source = source
        self._airports: dict[str, Airport] = {}
        self._region_cache: dict[str, tuple[list[str], float]] = {}

    async def region_codes(self, region: str) -> tuple[list[str], list[ProviderFailure]]:
        """
        Get the list of IATA codes for a region, caching the result.
        Returns the last good list if the refresh fails.
        """
        region_lower = region.lower()
        states = REGIONS.get(region_lower)
        if not states:
            return [], []

        now = time.monotonic()
        if region_lower in self._region_cache:
            codes, cached_at = self._region_cache[region_lower]
            if now - cached_at < settings.UNIVERSE_TTL_SECONDS:
                return codes, []

        codes, failures = await self._source.fetch_codes_by_states(states)
        if not failures and codes:
            self._region_cache[region_lower] = (codes, now)
        elif failures and region_lower in self._region_cache:
            # On failure, return the cached codes if we have them
            cached_codes, _ = self._region_cache[region_lower]
            return cached_codes, failures

        return codes, failures

    def get_cached_region_codes(self, region: str) -> list[str]:
        region_lower = region.lower()
        if region_lower in self._region_cache:
            return list(self._region_cache[region_lower][0])
        return []

    async def refresh(self, codes: Sequence[IATA]) -> list[ProviderFailure]:
        """
        Refresh the catalog from NTAD.
        Keeps the last good copy of an airport if the refresh fails or omits it.
        """
        airports, _, failures = await self._source.fetch_facilities(codes)

        for code, airport in airports.items():
            self._airports[code] = airport

        return failures

    def get(self, code: IATA) -> Airport | None:
        return self._airports.get(code)

    @property
    def codes(self) -> list[str]:
        return sorted(self._airports.keys())
