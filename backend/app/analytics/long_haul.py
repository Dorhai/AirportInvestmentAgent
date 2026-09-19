from __future__ import annotations

import math
from typing import Any

import pandas as pd

_EARTH_RADIUS_MI = 3958.8

LONG_HAUL_THRESHOLD_STATUTE_MILES = 3000.0


def haversine_miles(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance in statute miles."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    return _EARTH_RADIUS_MI * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_long_haul(
    distance_miles: float,
    threshold: float = LONG_HAUL_THRESHOLD_STATUTE_MILES,
) -> bool:
    return distance_miles >= threshold


def calculate_long_haul_percentage(
    df: pd.DataFrame,
    airport: str,
    threshold_miles: float = LONG_HAUL_THRESHOLD_STATUTE_MILES,
    start_year: int | None = None,
    end_year: int | None = None,
    passenger_only: bool = False,
) -> dict[str, Any]:
    """Calculate long-haul percentage and supporting stats from BTS T-100 data."""
    if df.empty:
        return _empty_result(airport, threshold_miles, start_year, end_year, passenger_only)

    mask = df["origin"] == airport
    if start_year is not None:
        mask &= df["year"] >= start_year
    if end_year is not None:
        mask &= df["year"] <= end_year
    
    if passenger_only:
        # Service class F = Scheduled Passenger, G = Scheduled Passenger/Cargo
        # If the dataset doesn't have service_class, we can't filter.
        if "service_class" in df.columns:
            mask &= df["service_class"].isin(["F", "G"])
        else:
            return _empty_result(airport, threshold_miles, start_year, end_year, passenger_only, passenger_filter_failed=True)

    filtered = df[mask]
    if filtered.empty:
        return _empty_result(airport, threshold_miles, start_year, end_year, passenger_only)

    total_departures = float(filtered["performed_departures"].sum())
    if total_departures <= 0:
        return _empty_result(airport, threshold_miles, start_year, end_year, passenger_only)

    long_haul_mask = filtered["distance_miles"] >= threshold_miles
    long_haul_df = filtered[long_haul_mask]
    
    long_haul_departures = float(long_haul_df["performed_departures"].sum())
    percentage = (long_haul_departures / total_departures) * 100.0

    unique_destinations = int(filtered["destination"].nunique())
    long_haul_destinations = int(long_haul_df["destination"].nunique())
    
    # Average distance weighted by departures
    total_distance_departures = (filtered["distance_miles"] * filtered["performed_departures"]).sum()
    avg_distance = float(total_distance_departures / total_departures) if total_departures > 0 else 0.0
    max_distance = float(filtered["distance_miles"].max()) if not filtered.empty else 0.0

    # Top long-haul routes
    top_routes = []
    if not long_haul_df.empty:
        route_totals = long_haul_df.groupby("destination")["performed_departures"].sum().reset_index()
        route_totals = route_totals.sort_values("performed_departures", ascending=False).head(5)
        for _, row in route_totals.iterrows():
            dest = row["destination"]
            deps = row["performed_departures"]
            # Get distance for this route (assume constant per route)
            dist = float(long_haul_df[long_haul_df["destination"] == dest]["distance_miles"].iloc[0])
            top_routes.append({
                "destination": dest,
                "distance_miles": dist,
                "departures": float(deps)
            })

    return {
        "airport": airport,
        "metric": "long_haul_departure_percentage",
        "threshold_miles": threshold_miles,
        "start_year": start_year,
        "end_year": end_year,
        "total_departures": total_departures,
        "long_haul_departures": long_haul_departures,
        "percentage": percentage,
        "passenger_only": passenger_only,
        "passenger_only_filter_available": "service_class" in df.columns,
        "unique_destinations": unique_destinations,
        "long_haul_destinations": long_haul_destinations,
        "average_distance_miles": avg_distance,
        "max_distance_miles": max_distance,
        "top_long_haul_routes": top_routes,
        "source": "BTS T-100 Segment",
        "calculation": "long_haul_departures / total_departures * 100"
    }

def _empty_result(
    airport: str, 
    threshold_miles: float, 
    start_year: int | None, 
    end_year: int | None, 
    passenger_only: bool,
    passenger_filter_failed: bool = False
) -> dict[str, Any]:
    return {
        "airport": airport,
        "metric": "long_haul_departure_percentage",
        "threshold_miles": threshold_miles,
        "start_year": start_year,
        "end_year": end_year,
        "total_departures": 0.0,
        "long_haul_departures": 0.0,
        "percentage": None,
        "passenger_only": passenger_only,
        "passenger_only_filter_available": not passenger_filter_failed,
        "unique_destinations": 0,
        "long_haul_destinations": 0,
        "average_distance_miles": 0.0,
        "max_distance_miles": 0.0,
        "top_long_haul_routes": [],
        "source": "BTS T-100 Segment",
        "calculation": "long_haul_departures / total_departures * 100"
    }
