"""Simulated script to download and parse FAA ATADS operations data."""

import json
import time
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "sample_airports.json"

def main() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # In a real scenario, this would download data from the FAA ATADS portal.
    # For now, we'll extract operations metrics from the sample data.
    
    with open(_SAMPLE_DATA, "r", encoding="utf-8") as f:
        sample_airports = json.load(f)

    mock_data = {}
    for data in sample_airports:
        code = data.get("iata_code")
        if not code:
            continue
        metrics = data.get("metrics", {})
        ao = metrics.get("annual_operations")
        if ao:
            mock_data[code] = {
                "annual_operations": ao["value"],
                "period": ao.get("prov", {}).get("period", "CY2024"),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
    
    out_path = _DATA_DIR / "faa_atads_operations.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f, indent=2)
    
    print(f"Wrote {len(mock_data)} records to {out_path}")

if __name__ == "__main__":
    main()
