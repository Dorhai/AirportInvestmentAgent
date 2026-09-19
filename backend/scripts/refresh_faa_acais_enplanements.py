"""Simulated script to download and parse FAA ACAIS enplanements data."""

import json
import time
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "sample_airports.json"

def main() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # In a real scenario, this would download a CSV or Excel file from the FAA website,
    # parse it, and extract the enplanements for the universe airports.
    # For now, we'll extract passenger metrics from the sample data.
    
    with open(_SAMPLE_DATA, "r", encoding="utf-8") as f:
        sample_airports = json.load(f)

    mock_data = {}
    for data in sample_airports:
        code = data.get("iata_code")
        if not code:
            continue
        metrics = data.get("metrics", {})
        pv = metrics.get("passenger_volume")
        ppv = metrics.get("previous_passenger_volume")
        if pv and ppv:
            mock_data[code] = {
                "passenger_volume": pv["value"],
                "previous_passenger_volume": ppv["value"],
                "period": pv.get("prov", {}).get("period", "CY2024"),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
    
    out_path = _DATA_DIR / "faa_acais_enplanements.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f, indent=2)
    
    print(f"Wrote {len(mock_data)} records to {out_path}")

if __name__ == "__main__":
    main()
