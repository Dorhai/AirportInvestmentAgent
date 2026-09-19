from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any
import zipfile

import pandas as pd

from app.models.airport import IATA, SUPPORTED
from app.models.metrics import Live, Present
from app.models.score import ProviderFailure
from app.providers.base import ProviderOutcome
from app.analytics.long_haul import calculate_long_haul_percentage, LONG_HAUL_THRESHOLD_STATUTE_MILES

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "bts"

class BtsT100FileProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._dir = path or _DATA_DIR
        self._by_origin: dict[str, pd.DataFrame] = {}
        self._metadata: dict[str, Any] = {
            "source": "BTS T-100 Segment",
            "latest_year": None,
            "latest_month": None,
            "retrieved_at": None,
        }
        self._load()

    def is_loaded(self) -> bool:
        return len(self._by_origin) > 0

    def _load(self) -> None:
        if not self._dir.exists():
            return

        files = list(self._dir.glob("*.csv")) + list(self._dir.glob("*.zip"))
        if not files:
            return

        # Load the first found file for simplicity
        file_path = files[0]
        logger.info("Loading BTS T-100 data from %s", file_path)

        try:
            if file_path.suffix == ".zip":
                with zipfile.ZipFile(file_path) as z:
                    csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                    if not csv_names:
                        logger.warning("No CSV found in %s", file_path)
                        return
                    with z.open(csv_names[0]) as f:
                        df = pd.read_csv(f, low_memory=False)
            else:
                df = pd.read_csv(file_path, low_memory=False)

            # Normalize columns case-insensitively
            col_map = {
                "ORIGIN": "origin",
                "DEST": "destination",
                "DESTINATION": "destination",
                "DISTANCE": "distance_miles",
                "DEPARTURES_PERFORMED": "performed_departures",
                "DEPPERFORMED": "performed_departures",
                "YEAR": "year",
                "MONTH": "month",
                "CLASS": "service_class",
                "PASSENGERS": "passengers",
            }
            
            # Create a case-insensitive map
            actual_cols = {c.upper(): c for c in df.columns}
            rename_dict = {}
            for k, v in col_map.items():
                if k in actual_cols:
                    rename_dict[actual_cols[k]] = v
            
            logger.info("BTS T-100 mapped columns: %s", list(rename_dict.values()))
            
            df = df.rename(columns=rename_dict)
            
            # Keep only needed columns
            keep_cols = [c for c in set(col_map.values()) if c in df.columns]
            df = df[keep_cols]

            # Drop missing essential columns
            req_cols = ["origin", "distance_miles", "performed_departures"]
            if not all(c in df.columns for c in req_cols):
                logger.warning("BTS T-100 missing required columns: %s", req_cols)
                return

            # Coerce and drop invalid
            df["distance_miles"] = pd.to_numeric(df["distance_miles"], errors="coerce")
            df["performed_departures"] = pd.to_numeric(df["performed_departures"], errors="coerce")
            df = df.dropna(subset=req_cols)
            df = df[df["performed_departures"] > 0]
            
            # Filter to supported peers only
            df = df[df["origin"].isin(SUPPORTED)]

            if "year" in df.columns and "month" in df.columns:
                self._metadata["latest_year"] = int(df["year"].max())
                self._metadata["latest_month"] = int(df[df["year"] == self._metadata["latest_year"]]["month"].max())
            
            import time
            self._metadata["retrieved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            # Build per-origin index
            self._by_origin = {
                origin: group 
                for origin, group in df.groupby("origin")
            }
            
            logger.info("BTS T-100 ready: %d rows, %d origins indexed", len(df), len(self._by_origin))

        except Exception as e:
            logger.error("Failed to load BTS T-100 data: %s", e)

    @property
    def name(self) -> str:
        return "BTS_T100"

    async def fetch(self, codes: Sequence[IATA]) -> ProviderOutcome:
        fields: dict[str, dict[str, Present]] = {}
        failures: list[ProviderFailure] = []

        if not self.is_loaded():
            return ProviderOutcome(fields=fields, failures=failures)

        period = "Unknown"
        if self._metadata["latest_year"]:
            period = f"{self._metadata['latest_year']}"
            if self._metadata["latest_month"]:
                period += f"-{self._metadata['latest_month']:02d}"

        origin = Live(
            source=self._metadata["source"],
            period=period,
            fetched_at=self._metadata["retrieved_at"] or "Unknown",
        )

        for code in codes:
            df = self._by_origin.get(code, pd.DataFrame())
            if df.empty:
                continue
                
            res = calculate_long_haul_percentage(
                df, 
                airport=code, 
                threshold_miles=LONG_HAUL_THRESHOLD_STATUTE_MILES,
                passenger_only=False
            )
            
            if res["total_departures"] > 0:
                fields[code] = {
                    "total_departures": Present[int](value=int(res["total_departures"]), origin=origin),
                    "long_haul_flights": Present[int](value=int(res["long_haul_departures"]), origin=origin),
                }

        return ProviderOutcome(fields=fields, failures=failures)

    def get_report(
        self, 
        airport: str, 
        threshold_miles: float = LONG_HAUL_THRESHOLD_STATUTE_MILES,
        start_year: int | None = None,
        end_year: int | None = None,
        passenger_only: bool = False
    ) -> dict[str, Any]:
        df = self._by_origin.get(airport, pd.DataFrame())
        res = calculate_long_haul_percentage(
            df, 
            airport=airport, 
            threshold_miles=threshold_miles,
            start_year=start_year,
            end_year=end_year,
            passenger_only=passenger_only
        )
        res["metadata"] = self._metadata
        return res
