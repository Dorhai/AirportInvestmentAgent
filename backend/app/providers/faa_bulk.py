from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

from app.models.airport import IATA
from app.models.metrics import Live, Present
from app.models.score import ProviderFailure
from app.providers.base import ProviderOutcome

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"

class FaaAcaisFileProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (_DATA_DIR / "faa_acais_enplanements.json")
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("FAA ACAIS cache file not found at %s", self._path)
            return
        with open(self._path, encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def name(self) -> str:
        return "FAA_ACAIS"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []

        for code in codes:
            entry = self._data.get(code)
            if entry is None:
                continue

            origin = Live(
                source="FAA ACAIS",
                period=entry.get("period", "Unknown"),
                fetched_at=entry.get("fetched_at", "Unknown"),
            )
            
            fields[code] = {
                "passenger_volume": Present[int](value=entry["passenger_volume"], origin=origin),
                "previous_passenger_volume": Present[int](value=entry["previous_passenger_volume"], origin=origin),
            }

        return ProviderOutcome(fields=fields, failures=failures)


class FaaAtadsFileProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (_DATA_DIR / "faa_atads_operations.json")
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("FAA ATADS cache file not found at %s", self._path)
            return
        with open(self._path, encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def name(self) -> str:
        return "FAA_ATADS"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []

        for code in codes:
            entry = self._data.get(code)
            if entry is None:
                continue

            origin = Live(
                source="FAA ATADS",
                period=entry.get("period", "Unknown"),
                fetched_at=entry.get("fetched_at", "Unknown"),
            )
            
            fields[code] = {
                "annual_operations": Present[int](value=entry["annual_operations"], origin=origin),
            }

        return ProviderOutcome(fields=fields, failures=failures)
