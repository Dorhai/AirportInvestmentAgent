from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from app.models.airport import IATA
from app.models.score import ProviderFailure
from app.providers.base import AviationProvider, ContextProvider, ContextOutcome, ProviderOutcome

logger = logging.getLogger(__name__)

class CompositeProvider:
    def __init__(
        self,
        providers: Sequence[AviationProvider],
    ) -> None:
        self._providers = list(providers)

    @property
    def name(self) -> str:
        return "Composite"

    async def fetch(self, codes: Sequence[IATA]) -> list[ProviderOutcome]:
        tasks = [provider.fetch(codes) for provider in self._providers]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ProviderOutcome] = []
        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                provider_name = getattr(self._providers[i], "name", f"provider_{i}")
                logger.warning("Provider %s raised: %s", provider_name, outcome)
                results.append(
                    ProviderOutcome(
                        fields={},
                        failures=[
                            ProviderFailure(
                                provider=provider_name,
                                error=str(outcome),
                            )
                        ],
                        warnings={},
                    )
                )
            else:
                results.append(outcome)

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
                        warnings={},
                    )
                )
            else:
                results.append(outcome)

        return results
