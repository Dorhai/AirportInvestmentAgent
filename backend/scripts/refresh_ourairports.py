"""Download OurAirports airports.csv and write a trimmed coordinate file."""

from __future__ import annotations

import csv
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
KEEP_COLUMNS = (
    "ident",
    "type",
    "iata_code",
    "gps_code",
    "latitude_deg",
    "longitude_deg",
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_OUT = _DATA_DIR / "ourairports_airports.csv"


def main() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL, timeout=120) as resp:
        raw = resp.read().decode("utf-8")

    reader = csv.DictReader(raw.splitlines())
    rows_written = 0
    with open(_OUT, "w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=KEEP_COLUMNS)
        writer.writeheader()
        for row in reader:
            lat = row.get("latitude_deg", "").strip()
            lon = row.get("longitude_deg", "").strip()
            if not lat or not lon:
                continue
            try:
                float(lat)
                float(lon)
            except ValueError:
                continue
            writer.writerow({k: row.get(k, "") for k in KEEP_COLUMNS})
            rows_written += 1

    print(f"Wrote {rows_written} rows to {_OUT}")


if __name__ == "__main__":
    try:
        main()
    except OSError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        sys.exit(1)
