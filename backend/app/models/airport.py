from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

IATA = Literal["BOS", "BDL", "PVD", "PWM", "LAX", "SNA", "ANC", "SFO", "JFK"]

SUPPORTED: frozenset[str] = frozenset(
    {"BOS", "BDL", "PVD", "PWM", "LAX", "SNA", "ANC", "SFO", "JFK"}
)

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
