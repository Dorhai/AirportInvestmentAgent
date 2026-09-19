from __future__ import annotations

from pydantic import BaseModel

from typing import Literal

class DelayProgram(BaseModel, frozen=True):
    airport_icao: str
    program: str
    reason: str
    avg_delay: str
    updated_at: str

class WeatherContext(BaseModel, frozen=True):
    flight_category: str
    wind: str
    visibility: str
    remarks: str
    observation_time: str

class ConnectivityContext(BaseModel, frozen=True):
    distinct_destinations: int
    international_destinations: int
    long_haul_route_count: int | None = None

class AirportContext(BaseModel, frozen=True):
    nas_delay_program: DelayProgram | None = None
    weather: WeatherContext | None = None
    connectivity: ConnectivityContext | None = None
    long_haul_departures: Literal["live", "unavailable"] | None = None
    warnings: list[str] = []
