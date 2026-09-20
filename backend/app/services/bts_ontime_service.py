from __future__ import annotations

import csv
import logging
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from app.analytics.bts_ontime import (
    AirportDelayMetrics,
    DelayBucket,
    DelayCauseBreakdown,
    DelayComparisonResult,
    MonthlyDelayPoint,
    aggregate_buckets,
    get_delay_causes,
    get_delay_trend,
)
from app.models.airport import IATA

logger = logging.getLogger(__name__)

def _csv_files_at(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".csv" else []
    if path.is_dir():
        return sorted(path.glob("*.csv"))
    return []


class BtsOnTimeService:
    def __init__(self, data_path: str | Path | None) -> None:
        self._data_path = Path(data_path) if data_path else None
        # Key: (airport, direction, date)
        self._buckets: dict[tuple[str, str, date], DelayBucket] = {}
        self._data_min_date: date | None = None
        self._data_max_date: date | None = None
        self._loaded_at: str | None = None
        self._staleness_warning: str | None = None
        self._is_loaded = False
        self._row_count = 0
        self._files_loaded: list[str] = []

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def data_min_date(self) -> date | None:
        return self._data_min_date

    @property
    def data_max_date(self) -> date | None:
        return self._data_max_date

    @property
    def loaded_at(self) -> str | None:
        return self._loaded_at

    @property
    def staleness_warning(self) -> str | None:
        return self._staleness_warning

    def load_sync(self) -> None:
        if not self._data_path or not self._data_path.exists():
            logger.warning("BTS On-Time CSV path not found or not configured: %s", self._data_path)
            return

        csv_files = _csv_files_at(self._data_path)
        if not csv_files:
            logger.warning("No BTS On-Time CSV to load at %s", self._data_path)
            return

        logger.info("Loading BTS On-Time data from %s", self._data_path)
        
        try:
                
            # Temporary mutable buckets during load
            # Key: (airport, direction, date)
            # Value: dict of counts/sums
            temp_buckets: dict[tuple[str, str, date], dict[str, float]] = defaultdict(
                lambda: {
                    "valid_flights": 0,
                    "delayed_15": 0,
                    "cancelled": 0,
                    "diverted": 0,
                    "delay_minutes": 0.0,
                    "carrier_delay": 0.0,
                    "weather_delay": 0.0,
                    "nas_delay": 0.0,
                    "security_delay": 0.0,
                    "late_aircraft_delay": 0.0,
                }
            )
            
            min_d = None
            max_d = None
            row_count = 0
            
            for csv_path in csv_files:
                self._files_loaded.append(csv_path.name)
                with open(csv_path, encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames:
                        continue
                        
                    # Map columns case-insensitively
                    cmap = {name.lower(): name for name in reader.fieldnames}
                    
                    def get_col(row, *possible_names):
                        for n in possible_names:
                            if n.lower() in cmap:
                                return row[cmap[n.lower()]]
                        return None
                        
                    for row in reader:
                        row_count += 1
                        
                        origin = get_col(row, "Origin", "ORIGIN")
                        dest = get_col(row, "Dest", "DEST")
                        flight_date_str = get_col(row, "FlightDate", "FL_DATE")
                        
                        if not origin or not dest or not flight_date_str:
                            continue
                            
                        try:
                            # Try YYYY-MM-DD or MM/DD/YYYY
                            if "-" in flight_date_str:
                                d = datetime.strptime(flight_date_str.split(" ")[0], "%Y-%m-%d").date()
                            else:
                                d = datetime.strptime(flight_date_str.split(" ")[0], "%m/%d/%Y").date()
                        except ValueError:
                            continue
                            
                        if min_d is None or d < min_d:
                            min_d = d
                        if max_d is None or d > max_d:
                            max_d = d
                            
                        def parse_flag(val) -> int:
                            if not val:
                                return 0
                            try:
                                return 1 if float(val) > 0 else 0
                            except ValueError:
                                return 1 if val.strip() == "1" else 0

                        cancelled = parse_flag(get_col(row, "Cancelled", "CANCELLED"))
                        diverted = parse_flag(get_col(row, "Diverted", "DIVERTED"))
                        
                        # Only count as valid if not cancelled
                        is_valid = 1 if cancelled == 0 else 0
                        
                        # Parse delays
                        def parse_float(val):
                            if not val:
                                return 0.0
                            try:
                                return float(val)
                            except ValueError:
                                return 0.0
                                
                        dep_del15 = 1 if parse_float(get_col(row, "DepDel15", "DEP_DEL15")) > 0 else 0
                        arr_del15 = 1 if parse_float(get_col(row, "ArrDel15", "ARR_DEL15")) > 0 else 0
                        
                        dep_delay_min = parse_float(
                            get_col(row, "DepDelayMinutes", "DEP_DELAY", "DEP_DELAY_NEW")
                        )
                        arr_delay_min = parse_float(
                            get_col(row, "ArrDelayMinutes", "ARR_DELAY", "ARR_DELAY_NEW")
                        )
                        
                        carrier_delay = parse_float(get_col(row, "CarrierDelay", "CARRIER_DELAY"))
                        weather_delay = parse_float(get_col(row, "WeatherDelay", "WEATHER_DELAY"))
                        nas_delay = parse_float(get_col(row, "NASDelay", "NAS_DELAY"))
                        security_delay = parse_float(get_col(row, "SecurityDelay", "SECURITY_DELAY"))
                        late_aircraft_delay = parse_float(
                            get_col(row, "LateAircraftDelay", "LATE_AIRCRAFT_DELAY")
                        )
                        
                        # Add to origin (departures)
                        b_dep = temp_buckets[(origin, "departures", d)]
                        b_dep["valid_flights"] += is_valid
                        b_dep["cancelled"] += cancelled
                        b_dep["diverted"] += diverted
                        if is_valid:
                            b_dep["delayed_15"] += dep_del15
                            b_dep["delay_minutes"] += dep_delay_min
                            b_dep["carrier_delay"] += carrier_delay
                            b_dep["weather_delay"] += weather_delay
                            b_dep["nas_delay"] += nas_delay
                            b_dep["security_delay"] += security_delay
                            b_dep["late_aircraft_delay"] += late_aircraft_delay
                            
                        # Add to dest (arrivals)
                        b_arr = temp_buckets[(dest, "arrivals", d)]
                        b_arr["valid_flights"] += is_valid
                        b_arr["cancelled"] += cancelled
                        b_arr["diverted"] += diverted
                        if is_valid:
                            b_arr["delayed_15"] += arr_del15
                            b_arr["delay_minutes"] += arr_delay_min
                            b_arr["carrier_delay"] += carrier_delay
                            b_arr["weather_delay"] += weather_delay
                            b_arr["nas_delay"] += nas_delay
                            b_arr["security_delay"] += security_delay
                            b_arr["late_aircraft_delay"] += late_aircraft_delay

            # Convert to immutable DelayBucket objects
            for (apt, dir_, d), vals in temp_buckets.items():
                self._buckets[(apt, dir_, d)] = DelayBucket(
                    airport=apt,
                    direction=dir_,
                    date=d,
                    valid_flights=int(vals["valid_flights"]),
                    delayed_15=int(vals["delayed_15"]),
                    cancelled=int(vals["cancelled"]),
                    diverted=int(vals["diverted"]),
                    delay_minutes=vals["delay_minutes"],
                    carrier_delay=vals["carrier_delay"],
                    weather_delay=vals["weather_delay"],
                    nas_delay=vals["nas_delay"],
                    security_delay=vals["security_delay"],
                    late_aircraft_delay=vals["late_aircraft_delay"],
                )
                
            self._data_min_date = min_d
            self._data_max_date = max_d
            self._row_count = row_count
            self._loaded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._is_loaded = True
            
            logger.info(
                "BTS On-Time ready: %d rows processed into %d daily buckets. Date range: %s to %s",
                row_count, len(self._buckets), min_d, max_d
            )
            
        except Exception as e:
            logger.error("Failed to load BTS On-Time data: %s", e)

    def _filter_buckets(
        self,
        airport: str,
        start_date: date | None,
        end_date: date | None,
        direction: Literal["departures", "arrivals", "both"],
    ) -> list[DelayBucket]:
        res = []
        for (apt, dir_, d), bucket in self._buckets.items():
            if apt != airport:
                continue
            if direction != "both" and dir_ != direction:
                continue
            if start_date and d < start_date:
                continue
            if end_date and d > end_date:
                continue
            res.append(bucket)
        return res

    def get_airport_delay_metrics(
        self,
        airport: IATA,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        direction: Literal["departures", "arrivals", "both"] = "both",
    ) -> AirportDelayMetrics | None:
        if not self._is_loaded:
            return None
            
        buckets = self._filter_buckets(airport, start_date, end_date, direction)
        if not buckets:
            return None
            
        eff_min = start_date or self._data_min_date
        eff_max = end_date or self._data_max_date
            
        return aggregate_buckets(airport, buckets, eff_min, eff_max)

    def compare_airport_delays(
        self,
        airport_a: IATA,
        airport_b: IATA,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> DelayComparisonResult | None:
        if not self._is_loaded:
            return None
            
        metrics_a = self.get_airport_delay_metrics(airport_a, start_date=start_date, end_date=end_date)
        metrics_b = self.get_airport_delay_metrics(airport_b, start_date=start_date, end_date=end_date)
        
        if not metrics_a or not metrics_b:
            return None
            
        eff_min = start_date or self._data_min_date
        eff_max = end_date or self._data_max_date
        
        from app.analytics.bts_ontime import build_period_label
        
        return DelayComparisonResult(
            airport_a=metrics_a,
            airport_b=metrics_b,
            period=build_period_label(eff_min, eff_max),
        )

    def get_delay_causes(
        self,
        airport: IATA,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        direction: Literal["departures", "arrivals"] = "departures",
    ) -> DelayCauseBreakdown | None:
        if not self._is_loaded:
            return None
            
        buckets = self._filter_buckets(airport, start_date, end_date, direction)
        if not buckets:
            return None
            
        eff_min = start_date or self._data_min_date
        eff_max = end_date or self._data_max_date
            
        return get_delay_causes(airport, buckets, eff_min, eff_max, direction)

    def get_delay_trend(
        self,
        airport: IATA,
        *,
        direction: Literal["departures", "arrivals"] = "departures",
    ) -> list[MonthlyDelayPoint] | None:
        if not self._is_loaded:
            return None
            
        buckets = self._filter_buckets(airport, None, None, direction)
        if not buckets:
            return None
            
        return get_delay_trend(buckets, direction)
