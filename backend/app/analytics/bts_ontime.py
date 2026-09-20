from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class DelayBucket(BaseModel, frozen=True):
    """Daily rollup of delays for a specific airport and direction."""
    airport: str
    direction: Literal["departures", "arrivals"]
    date: date
    valid_flights: int
    delayed_15: int
    cancelled: int
    diverted: int
    delay_minutes: float
    carrier_delay: float
    weather_delay: float
    nas_delay: float
    security_delay: float
    late_aircraft_delay: float


class DelayCauseBreakdown(BaseModel, frozen=True):
    airport: str
    period: str
    direction: Literal["departures", "arrivals"]
    total_flights: int
    carrier_delay_pct: float
    weather_delay_pct: float
    nas_delay_pct: float
    security_delay_pct: float
    late_aircraft_delay_pct: float
    primary_delay_cause: str | None
    source: str = "BTS Reporting Carrier On-Time Performance"
    assumptions: list[str] = []


class AirportDelayMetrics(BaseModel, frozen=True):
    airport: str
    period: str
    total_flights: int
    departure_delay_pct: float | None
    arrival_delay_pct: float | None
    average_departure_delay_minutes: float | None
    average_arrival_delay_minutes: float | None
    cancellation_pct: float
    diversion_pct: float
    primary_delay_cause: str | None
    source: str = "BTS Reporting Carrier On-Time Performance"
    assumptions: list[str] = []


class MonthlyDelayPoint(BaseModel, frozen=True):
    year: int
    month: int
    total_flights: int
    delay_pct: float
    average_delay_minutes: float
    cancellation_pct: float


class DelayComparisonResult(BaseModel, frozen=True):
    airport_a: AirportDelayMetrics
    airport_b: AirportDelayMetrics
    period: str
    source: str = "BTS Reporting Carrier On-Time Performance"


def build_period_label(min_date: date | None, max_date: date | None) -> str:
    if not min_date or not max_date:
        return "unknown period"
    return f"{min_date.strftime('%Y-%m')} to {max_date.strftime('%Y-%m')}"


def aggregate_buckets(
    airport: str,
    buckets: list[DelayBucket],
    min_date: date | None,
    max_date: date | None,
) -> AirportDelayMetrics:
    dep_valid = 0
    dep_delayed = 0
    dep_minutes = 0.0
    
    arr_valid = 0
    arr_delayed = 0
    arr_minutes = 0.0

    total_flights = 0
    cancelled = 0
    diverted = 0
    
    # Causes (we'll sum both dep and arr for the primary cause, or just dep)
    # The plan says: "Use summed delay minutes to determine the main causes of delays."
    causes = {
        "Carrier": 0.0,
        "Weather": 0.0,
        "NAS": 0.0,
        "Security": 0.0,
        "LateAircraft": 0.0,
    }

    for b in buckets:
        total_flights += b.valid_flights + b.cancelled + b.diverted
        cancelled += b.cancelled
        diverted += b.diverted
        
        causes["Carrier"] += b.carrier_delay
        causes["Weather"] += b.weather_delay
        causes["NAS"] += b.nas_delay
        causes["Security"] += b.security_delay
        causes["LateAircraft"] += b.late_aircraft_delay
        
        if b.direction == "departures":
            dep_valid += b.valid_flights
            dep_delayed += b.delayed_15
            dep_minutes += b.delay_minutes
        else:
            arr_valid += b.valid_flights
            arr_delayed += b.delayed_15
            arr_minutes += b.delay_minutes

    dep_pct = (dep_delayed / dep_valid * 100.0) if dep_valid > 0 else None
    arr_pct = (arr_delayed / arr_valid * 100.0) if arr_valid > 0 else None
    
    avg_dep_min = (dep_minutes / dep_valid) if dep_valid > 0 else None
    avg_arr_min = (arr_minutes / arr_valid) if arr_valid > 0 else None
    
    cancel_pct = (cancelled / total_flights * 100.0) if total_flights > 0 else 0.0
    divert_pct = (diverted / total_flights * 100.0) if total_flights > 0 else 0.0
    
    primary_cause = None
    if sum(causes.values()) > 0:
        primary_cause = max(causes.items(), key=lambda x: x[1])[0]

    return AirportDelayMetrics(
        airport=airport,
        period=build_period_label(min_date, max_date),
        total_flights=total_flights,
        departure_delay_pct=dep_pct,
        arrival_delay_pct=arr_pct,
        average_departure_delay_minutes=avg_dep_min,
        average_arrival_delay_minutes=avg_arr_min,
        cancellation_pct=cancel_pct,
        diversion_pct=divert_pct,
        primary_delay_cause=primary_cause,
        assumptions=["Cancelled flights excluded from delay averages"] if cancelled > 0 else []
    )


def get_delay_causes(
    airport: str,
    buckets: list[DelayBucket],
    min_date: date | None,
    max_date: date | None,
    direction: Literal["departures", "arrivals"] = "departures",
) -> DelayCauseBreakdown:
    total_flights = 0
    causes = {
        "Carrier": 0.0,
        "Weather": 0.0,
        "NAS": 0.0,
        "Security": 0.0,
        "LateAircraft": 0.0,
    }
    
    for b in buckets:
        if b.direction != direction:
            continue
            
        total_flights += b.valid_flights + b.cancelled + b.diverted
        causes["Carrier"] += b.carrier_delay
        causes["Weather"] += b.weather_delay
        causes["NAS"] += b.nas_delay
        causes["Security"] += b.security_delay
        causes["LateAircraft"] += b.late_aircraft_delay
        
    total_cause_minutes = sum(causes.values())
    
    pcts = {k: (v / total_cause_minutes * 100.0) if total_cause_minutes > 0 else 0.0 for k, v in causes.items()}
    
    primary_cause = None
    if total_cause_minutes > 0:
        primary_cause = max(causes.items(), key=lambda x: x[1])[0]
        
    return DelayCauseBreakdown(
        airport=airport,
        period=build_period_label(min_date, max_date),
        direction=direction,
        total_flights=total_flights,
        carrier_delay_pct=pcts["Carrier"],
        weather_delay_pct=pcts["Weather"],
        nas_delay_pct=pcts["NAS"],
        security_delay_pct=pcts["Security"],
        late_aircraft_delay_pct=pcts["LateAircraft"],
        primary_delay_cause=primary_cause,
    )


def get_delay_trend(
    buckets: list[DelayBucket],
    direction: Literal["departures", "arrivals"] = "departures",
) -> list[MonthlyDelayPoint]:
    # Group by year, month
    monthly: dict[tuple[int, int], dict[str, float]] = {}
    
    for b in buckets:
        if b.direction != direction:
            continue
            
        key = (b.date.year, b.date.month)
        if key not in monthly:
            monthly[key] = {
                "valid": 0,
                "delayed": 0,
                "cancelled": 0,
                "diverted": 0,
                "minutes": 0.0,
            }
            
        m = monthly[key]
        m["valid"] += b.valid_flights
        m["delayed"] += b.delayed_15
        m["cancelled"] += b.cancelled
        m["diverted"] += b.diverted
        m["minutes"] += b.delay_minutes
        
    points: list[MonthlyDelayPoint] = []
    for (year, month), m in sorted(monthly.items()):
        total = m["valid"] + m["cancelled"] + m["diverted"]
        valid = m["valid"]
        
        delay_pct = (m["delayed"] / valid * 100.0) if valid > 0 else 0.0
        avg_min = (m["minutes"] / valid) if valid > 0 else 0.0
        cancel_pct = (m["cancelled"] / total * 100.0) if total > 0 else 0.0
        
        points.append(MonthlyDelayPoint(
            year=year,
            month=month,
            total_flights=int(total),
            delay_pct=delay_pct,
            average_delay_minutes=avg_min,
            cancellation_pct=cancel_pct,
        ))
        
    return points
