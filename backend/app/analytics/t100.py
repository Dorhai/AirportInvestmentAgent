from __future__ import annotations

from datetime import date
from typing import Sequence
from collections import defaultdict

from pydantic import BaseModel

class MonthlyTraffic(BaseModel, frozen=True):
    code: str
    month: date
    departures: int
    passengers: int
    seats: int
    intl_departures: int
    avg_distance_sm: float | None = None

class TrailingWindow(BaseModel, frozen=True):
    start: date
    end: date
    months: int
    passengers: int
    departures: int
    seats: int
    intl_departures: int
    avg_distance_sm: float | None = None

class TrailingComparison(BaseModel, frozen=True):
    current: TrailingWindow
    previous: TrailingWindow
    period_label: str

def latest_complete_month(rows: Sequence[MonthlyTraffic]) -> date | None:
    if not rows:
        return None
    return max(r.month for r in rows)

def trailing_windows(rows: Sequence[MonthlyTraffic], months: int = 12) -> dict[str, TrailingComparison]:
    """
    Per code. Only codes with all `months` present in BOTH windows are returned;
    others are omitted (caller emits Absent).
    """
    if not rows:
        return {}

    latest = latest_complete_month(rows)
    if not latest:
        return {}
    
    # Calculate start and end dates for current and previous windows
    # end of current window is `latest`
    # start of current window is `latest` minus (months - 1) months
    def subtract_months(d: date, m: int) -> date:
        y, mo = divmod(d.month - 1 - m, 12)
        return date(d.year + y, mo + 1, 1)
    
    current_end = latest
    current_start = subtract_months(latest, months - 1)
    
    previous_end = subtract_months(current_end, months)
    previous_start = subtract_months(current_start, months)
    
    by_code: dict[str, list[MonthlyTraffic]] = defaultdict(list)
    for r in rows:
        by_code[r.code].append(r)
        
    result: dict[str, TrailingComparison] = {}
    
    def _weighted_avg_distance(rows: list[MonthlyTraffic]) -> float | None:
        valid_rows = [r for r in rows if r.avg_distance_sm is not None]
        if not valid_rows:
            return None
        total_deps = sum(r.departures for r in valid_rows)
        if total_deps == 0:
            return None
        return sum(r.avg_distance_sm * r.departures for r in valid_rows) / total_deps

    for code, code_rows in by_code.items():
        current_rows = [r for r in code_rows if current_start <= r.month <= current_end]
        previous_rows = [r for r in code_rows if previous_start <= r.month <= previous_end]
        
        if len(current_rows) == months and len(previous_rows) == months:
            current_window = TrailingWindow(
                start=current_start,
                end=current_end,
                months=months,
                passengers=sum(r.passengers for r in current_rows),
                departures=sum(r.departures for r in current_rows),
                seats=sum(r.seats for r in current_rows),
                intl_departures=sum(r.intl_departures for r in current_rows),
                avg_distance_sm=_weighted_avg_distance(current_rows)
            )
            previous_window = TrailingWindow(
                start=previous_start,
                end=previous_end,
                months=months,
                passengers=sum(r.passengers for r in previous_rows),
                departures=sum(r.departures for r in previous_rows),
                seats=sum(r.seats for r in previous_rows),
                intl_departures=sum(r.intl_departures for r in previous_rows),
                avg_distance_sm=_weighted_avg_distance(previous_rows)
            )
            
            period_label = f"{current_start.strftime('%Y-%m')}..{current_end.strftime('%Y-%m')} vs {previous_start.strftime('%Y-%m')}..{previous_end.strftime('%Y-%m')}"
            
            result[code] = TrailingComparison(
                current=current_window,
                previous=previous_window,
                period_label=period_label
            )
            
    return result
