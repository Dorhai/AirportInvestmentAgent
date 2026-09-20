from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Any

import httpx

from app.models.airport import IATA
from app.models.context import DelayProgram
from app.models.score import ProviderFailure
from app.providers.base import ContextOutcome

logger = logging.getLogger(__name__)

class FaaNasProvider:
    _URL = "https://nasstatus.faa.gov/api/airport-status-information"

    def __init__(self, http: httpx.AsyncClient, timeout_s: float) -> None:
        self._http = http
        self._timeout = timeout_s

    @property
    def name(self) -> str:
        return "FAA_NAS"

    async def fetch(self, codes: Sequence[IATA]) -> ContextOutcome:
        contexts: dict[str, dict[str, Any]] = {}
        failures: list[ProviderFailure] = []

        programs = await self._fetch_programs()
        if programs is None:
            failures.append(
                ProviderFailure(provider=self.name, error="Failed to fetch NAS status")
            )
            return ContextOutcome(fields=contexts, failures=failures, warnings={})

        for code in codes:
            matching = [p for p in programs if p.airport_icao.endswith(code)]
            if matching:
                contexts[code] = {
                    "nas_delay_program": matching[0],
                }

        return ContextOutcome(fields=contexts, failures=failures, warnings={})

    async def _fetch_programs(self) -> list[DelayProgram] | None:
        try:
            resp = await self._http.get(self._URL, timeout=self._timeout)
            resp.raise_for_status()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("FAA NAS request failed: %s", exc)
            return None

        return self._parse_xml(resp.text)

    @staticmethod
    def _parse_xml(xml_text: str) -> list[DelayProgram]:
        programs: list[DelayProgram] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse FAA NAS XML")
            return programs

        for delay_el in root.iter("Delay"):
            arpt = delay_el.findtext("ARPT", "")
            program = delay_el.findtext("Reason", "")
            reason = delay_el.findtext("Type", "")
            avg_delay = delay_el.findtext("Avg", "")
            updated = delay_el.findtext("Updated", "")

            if arpt:
                programs.append(
                    DelayProgram(
                        airport_icao=arpt,
                        program=program,
                        reason=reason,
                        avg_delay=avg_delay,
                        updated_at=updated,
                    )
                )
        return programs
