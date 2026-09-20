from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field

IATA = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]

_IATA_RE = re.compile(r"^[A-Z]{3}$")


def normalize_iata(code: str) -> str:
    upper = code.strip().upper()
    if not _IATA_RE.match(upper):
        raise ValueError(f"{code!r} is not a valid IATA code (expected 3 letters)")
    return upper


Region = Literal["new_england", "west_coast", "alaska", "northeast", "california"]

REGIONS: dict[str, frozenset[str]] = {
    "new_england": frozenset({"ME", "NH", "VT", "MA", "RI", "CT"}),
    "west_coast": frozenset({"WA", "OR", "CA"}),
    "alaska": frozenset({"AK"}),
    "northeast": frozenset({"NY", "NJ", "PA", "CT", "MA", "RI"}),
    "california": frozenset({"CA"}),
}


class Airport(BaseModel, frozen=True):
    iata_code: IATA
    icao_code: str
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
