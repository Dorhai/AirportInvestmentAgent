from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.models.airport import IATA
from app.models.context import ConnectivityContext
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


class OpenFlightsRoutesProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (_DATA_DIR / "openflights_routes.json")
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("OpenFlights cache file not found at %s", self._path)
            return
        with open(self._path, encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def name(self) -> str:
        return "OpenFlights"

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        fields: dict[str, dict[str, Any]] = {}
        failures: list[ProviderFailure] = []

        for code in codes:
            entry = self._data.get(code)
            if entry is None:
                continue

            fields[code] = {
                "connectivity": ConnectivityContext(
                    distinct_destinations=entry.get("distinct_destinations", 0),
                    international_destinations=entry.get("international_destinations", 0),
                    long_haul_route_count=entry.get("long_haul_route_count", 0),
                )
            }

        return ContextOutcome(fields=fields, failures=failures)
