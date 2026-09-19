"""Simulated script to download and parse OpenFlights routes data."""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "sample_airports.json"

def main() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # In a real scenario, this would download routes.dat from OpenFlights,
    # parse it, and extract the connectivity summaries for the universe airports.
    # For now, we'll extract connectivity context from the sample data if it exists,
    # or provide some reasonable fake data for the 9 peers.
    
    with open(_SAMPLE_DATA, "r", encoding="utf-8") as f:
        sample_airports = json.load(f)

    mock_data = {}
    for data in sample_airports:
        code = data.get("iata_code")
        if not code:
            continue
        mock_data[code] = {
            "distinct_destinations": 120,
            "international_destinations": 30,
            "long_haul_route_count": 15
        }
    
    out_path = _DATA_DIR / "openflights_routes.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f, indent=2)
    
    print(f"Wrote {len(mock_data)} records to {out_path}")

if __name__ == "__main__":
    main()
