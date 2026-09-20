from __future__ import annotations

from typing import Any
from pydantic import BaseModel

LONG_HAUL_THRESHOLD_STATUTE_MILES = 3000.0

class SegmentRow(BaseModel, frozen=True):
    origin: str
    dest: str
    distance_miles: float
    departures: float
    passengers: float
    year: int
    month: int
    service_class: str

class LongHaulSummary(BaseModel, frozen=True):
    pct: float
    total_departures: float
    long_haul_departures: float
    unique_destinations: int
    long_haul_destinations: int
    average_distance_miles: float
    max_distance_miles: float
    top_long_haul_routes: list[dict[str, Any]]
    start_year: int | None
    end_year: int | None

def summarize_long_haul(
    rows: list[SegmentRow],
    threshold: float = LONG_HAUL_THRESHOLD_STATUTE_MILES,
    passenger_only: bool = False,
) -> LongHaulSummary | None:
    if not rows:
        return None

    if passenger_only:
        rows = [r for r in rows if r.service_class in ("F", "G")]
        if not rows:
            return None

    total_departures = 0.0
    long_haul_departures = 0.0
    destinations = set()
    long_haul_destinations = set()
    max_distance = 0.0
    sum_distance_x_departures = 0.0
    
    # For top routes
    route_departures: dict[str, float] = {}
    route_distances: dict[str, float] = {}

    start_year = min(r.year for r in rows)
    end_year = max(r.year for r in rows)

    for r in rows:
        total_departures += r.departures
        destinations.add(r.dest)
        sum_distance_x_departures += (r.distance_miles * r.departures)
        
        if r.distance_miles > max_distance:
            max_distance = r.distance_miles
            
        if r.distance_miles >= threshold:
            long_haul_departures += r.departures
            long_haul_destinations.add(r.dest)
            
            route_departures[r.dest] = route_departures.get(r.dest, 0.0) + r.departures
            route_distances[r.dest] = r.distance_miles

    if total_departures == 0:
        return None

    pct = (long_haul_departures / total_departures) * 100.0
    avg_dist = sum_distance_x_departures / total_departures

    # Top 5 long haul routes by departures
    top_routes = []
    sorted_dests = sorted(route_departures.keys(), key=lambda d: route_departures[d], reverse=True)
    for dest in sorted_dests[:5]:
        top_routes.append({
            "destination": dest,
            "departures": route_departures[dest],
            "distance_miles": route_distances[dest]
        })

    return LongHaulSummary(
        pct=pct,
        total_departures=total_departures,
        long_haul_departures=long_haul_departures,
        unique_destinations=len(destinations),
        long_haul_destinations=len(long_haul_destinations),
        average_distance_miles=avg_dist,
        max_distance_miles=max_distance,
        top_long_haul_routes=top_routes,
        start_year=start_year,
        end_year=end_year,
    )