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

class FacilityContext(BaseModel, frozen=True):
    acreage: int | None
    part139_class: str | None
    tower_type: str | None
    status: str | None
    effective_date: str
    source: str = "NTAD Aviation Facilities"

class NationalTrafficContext(BaseModel, frozen=True):
    period: str
    passengers_12m: int
    passengers_prev_12m: int
    growth_pct: float
    departures_12m: int
    load_factor_pct: float
    source: str = "BTS AFF T-100 Summary"

class AirportContext(BaseModel, frozen=True):
    nas_delay_program: DelayProgram | None = None
    weather: WeatherContext | None = None
    facility: FacilityContext | None = None
    national_traffic: NationalTrafficContext | None = None
    long_haul_departures: Literal["live", "unavailable"] | None = None
    warnings: list[str] = []
