from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from app.models.airport import IATA, Airport

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


class CoordinateLookup:
    def __init__(
        self,
        ourairports_path: Path | None = None,
        overlay_path: Path | None = None,
    ) -> None:
        self._ourairports_path = ourairports_path or (
            _DATA_DIR / "ourairports_airports.csv"
        )
        self._overlay_path = overlay_path or (_DATA_DIR / "airport_coords.csv")
        self._by_icao: dict[str, tuple[float, float]] = {}
        self._iata_to_icao: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._ourairports_path.is_file():
            self._load_ourairports(self._ourairports_path)
        else:
            logger.warning(
                "OurAirports file missing at %s; long-haul dest lookup will be limited",
                self._ourairports_path,
            )
        if self._overlay_path.is_file():
            self._load_overlay(self._overlay_path)

    def _load_ourairports(self, path: Path) -> None:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lat_s = row.get("latitude_deg", "").strip()
                lon_s = row.get("longitude_deg", "").strip()
                if not lat_s or not lon_s:
                    continue
                try:
                    lat, lon = float(lat_s), float(lon_s)
                except ValueError:
                    continue
                ident = row.get("ident", "").strip().upper()
                gps = row.get("gps_code", "").strip().upper()
                if ident:
                    self._by_icao.setdefault(ident, (lat, lon))
                if gps and gps != ident:
                    self._by_icao.setdefault(gps, (lat, lon))

    def _load_overlay(self, path: Path) -> None:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                icao = row["icao_code"].strip().upper()
                iata = row["iata_code"].strip().upper()
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                self._by_icao[icao] = (lat, lon)
                self._iata_to_icao[iata] = icao

    def get(self, icao: str) -> tuple[float, float] | None:
        return self._by_icao.get(icao.strip().upper())

    def icao_for(self, iata: str) -> str | None:
        return self._iata_to_icao.get(iata.strip().upper())


class AirportCatalog:
    def __init__(self, sample_path: Path | None = None) -> None:
        self._path = sample_path or (_DATA_DIR / "sample_airports.json")
        self._airports: dict[str, Airport] = {}
        self._load()

    def _load(self) -> None:
        with open(self._path, encoding="utf-8") as f:
            raw: list[dict] = json.load(f)
        for entry in raw:
            airport = Airport(
                iata_code=entry["iata_code"],
                icao_code=entry["icao_code"],
                name=entry["name"],
                city=entry["city"],
                state=entry["state"],
                latitude=entry["latitude"],
                longitude=entry["longitude"],
            )
            self._airports[airport.iata_code] = airport

    def get(self, code: IATA) -> Airport | None:
        return self._airports.get(code)

    @property
    def codes(self) -> list[str]:
        return list(self._airports)
