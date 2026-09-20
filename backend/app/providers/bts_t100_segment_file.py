from __future__ import annotations

import csv
import logging
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.analytics.long_haul import SegmentRow

logger = logging.getLogger(__name__)

class BtsT100SegmentFileProvider:
    def __init__(self, path: str | Path | None) -> None:
        self._path = Path(path) if path else None
        self._by_origin: dict[str, list[SegmentRow]] = defaultdict(list)
        self._period_label: str | None = None
        self._retrieved_at: str | None = None
        self._staleness_warning: str | None = None
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def period_label(self) -> str | None:
        return self._period_label

    @property
    def retrieved_at(self) -> str | None:
        return self._retrieved_at

    @property
    def staleness_warning(self) -> str | None:
        return self._staleness_warning

    def rows_for(self, code: str) -> list[SegmentRow]:
        return self._by_origin.get(code, [])

    def load_sync(self) -> None:
        if not self._path or not self._path.exists():
            logger.warning("BTS T-100 Segment file not found or not configured: %s", self._path)
            return

        logger.info("Loading BTS T-100 Segment data from %s", self._path)
        
        try:
            mtime = self._path.stat().st_mtime
            self._retrieved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
            
            if self._path.suffix.lower() == ".zip":
                with zipfile.ZipFile(self._path) as z:
                    csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                    if not csv_names:
                        logger.warning("No CSV found in %s", self._path)
                        return
                    with z.open(csv_names[0]) as f:
                        # ZipExtFile reads as bytes, csv needs strings
                        import io
                        text_f = io.TextIOWrapper(f, encoding="utf-8-sig")
                        self._read_csv(text_f)
            else:
                with open(self._path, encoding="utf-8-sig") as f:
                    self._read_csv(f)
                    
            self._is_loaded = True
            logger.info("BTS T-100 Segment ready: %d origins indexed", len(self._by_origin))
            
        except Exception as e:
            logger.error("Failed to load BTS T-100 Segment data: %s", e)

    def _read_csv(self, f) -> None:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return
            
        # Map columns case-insensitively
        actual_cols = {c.upper(): c for c in reader.fieldnames if c}
        
        col_map = {
            "ORIGIN": "origin",
            "DEST": "dest",
            "DESTINATION": "dest",
            "DISTANCE": "distance_miles",
            "DEPARTURES_PERFORMED": "departures",
            "DEPPERFORMED": "departures",
            "PASSENGERS": "passengers",
            "YEAR": "year",
            "MONTH": "month",
            "CLASS": "service_class",
        }
        
        # Determine the actual column names in the file
        mapped_keys = {}
        for k, v in col_map.items():
            if k in actual_cols:
                mapped_keys[v] = actual_cols[k]
                
        req_keys = ["origin", "dest", "distance_miles", "departures"]
        if not all(k in mapped_keys for k in req_keys):
            logger.warning("BTS T-100 Segment missing required columns. Found: %s", reader.fieldnames)
            return
            
        min_year_month = None
        max_year_month = None
        
        for row in reader:
            try:
                deps = float(row[mapped_keys["departures"]] or 0)
                if deps <= 0:
                    continue
                    
                origin = str(row[mapped_keys["origin"]]).strip()
                dest = str(row[mapped_keys["dest"]]).strip()
                dist = float(row[mapped_keys["distance_miles"]] or 0)
                pax = float(row.get(mapped_keys.get("passengers", ""), 0) or 0)
                
                year_str = row.get(mapped_keys.get("year", ""))
                month_str = row.get(mapped_keys.get("month", ""))
                year = int(year_str) if year_str else 0
                month = int(month_str) if month_str else 0
                
                svc_class = str(row.get(mapped_keys.get("service_class", ""), "")).strip()
                
                if year > 0 and month > 0:
                    ym = (year, month)
                    if min_year_month is None or ym < min_year_month:
                        min_year_month = ym
                    if max_year_month is None or ym > max_year_month:
                        max_year_month = ym
                
                self._by_origin[origin].append(SegmentRow(
                    origin=origin,
                    dest=dest,
                    distance_miles=dist,
                    departures=deps,
                    passengers=pax,
                    year=year,
                    month=month,
                    service_class=svc_class
                ))
            except (ValueError, TypeError):
                continue
                
        if min_year_month and max_year_month:
            self._period_label = f"{min_year_month[0]}-{min_year_month[1]:02d}..{max_year_month[0]}-{max_year_month[1]:02d}"
            
            # Check staleness (older than 18 months)
            now = datetime.utcnow()
            months_old = (now.year - max_year_month[0]) * 12 + now.month - max_year_month[1]
            if months_old > 18:
                self._staleness_warning = f"BTS T-100 Segment data is {months_old} months old (latest: {max_year_month[0]}-{max_year_month[1]:02d})"