from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from pathlib import Path

from app.models.airport import IATA
from app.models.metrics import Present, Sample
from app.models.score import ProviderFailure
from app.providers.base import AviationProvider, ContextProvider, ContextOutcome, ProviderOutcome

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _to_sample_origin(prov: dict) -> Sample:
    return Sample(
        source=prov.get("source", "sample"),
        period=prov.get("period", ""),
        citation=prov.get("citation", ""),
    )


class SampleProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (_DATA_DIR / "sample_airports.json")
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        with open(self._path, encoding="utf-8") as f:
            raw: list[dict] = json.load(f)
        for entry in raw:
            code = entry["iata_code"]
            self._data[code] = entry

    @property
    def name(self) -> str:
        return "SampleData"

    @property
    def codes(self) -> list[str]:
        return list(self._data)

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []

        for code in codes:
            entry = self._data.get(code)
            if entry is None:
                failures.append(
                    ProviderFailure(
                        provider=self.name,
                        error=f"No sample data for {code}",
                    )
                )
                continue

            raw_metrics: dict = entry.get("metrics", {})
            airport_fields: dict[str, Present] = {}

            _FIELD_MAP: dict[str, type] = {
                "passenger_volume": int,
                "previous_passenger_volume": int,
                "annual_operations": int,
                "delayed_flights_pct": float,
                "average_delay_minutes": float,
            }

            for field_name, typ in _FIELD_MAP.items():
                metric_entry = raw_metrics.get(field_name)
                if metric_entry is None:
                    continue
                value = typ(metric_entry["value"])
                origin = _to_sample_origin(metric_entry["prov"])
                airport_fields[field_name] = Present[typ](value=value, origin=origin)  # type: ignore[valid-type]

            fields[code] = airport_fields

        return ProviderOutcome(fields=fields, failures=failures)


class CompositeProvider:
    def __init__(
        self,
        live: Sequence[AviationProvider],
        sample: SampleProvider,
    ) -> None:
        self._live = list(live)
        self._sample = sample

    @property
    def name(self) -> str:
        return "Composite"

    async def fetch(self, codes: Sequence[IATA]) -> list[ProviderOutcome]:
        live_tasks = [provider.fetch(codes) for provider in self._live]
        live_outcomes = await asyncio.gather(*live_tasks, return_exceptions=True)

        results: list[ProviderOutcome] = []
        for i, outcome in enumerate(live_outcomes):
            if isinstance(outcome, BaseException):
                provider_name = getattr(self._live[i], "name", f"live_{i}")
                logger.warning("Live provider %s raised: %s", provider_name, outcome)
                results.append(
                    ProviderOutcome(
                        fields={},
                        failures=[
                            ProviderFailure(
                                provider=provider_name,
                                error=str(outcome),
                            )
                        ],
                    )
                )
            else:
                results.append(outcome)

        sample_outcome = await self._sample.fetch(codes)
        results.append(sample_outcome)

        return results


class ContextComposite:
    def __init__(self, providers: Sequence[ContextProvider]) -> None:
        self._providers = list(providers)

    async def fetch(self, codes: Sequence[IATA]) -> list[ContextOutcome]:
        tasks = [provider.fetch(codes) for provider in self._providers]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ContextOutcome] = []
        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                provider_name = getattr(self._providers[i], "name", f"context_{i}")
                logger.warning("Context provider %s raised: %s", provider_name, outcome)
                results.append(
                    ContextOutcome(
                        fields={},
                        failures=[
                            ProviderFailure(
                                provider=provider_name,
                                error=str(outcome),
                            )
                        ],
                    )
                )
            else:
                results.append(outcome)

        return results
