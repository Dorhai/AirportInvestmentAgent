# BTS T-100 Segment Data

## What it is
The Bureau of Transportation Statistics (BTS) T-100 Segment dataset contains domestic and international non-stop segment data reported by U.S. and foreign air carriers.

## Why we use it
OpenSky provides live state-vector data, which is useful for current traffic but not for historical, aggregated route analysis. BTS T-100 provides reliable historical route, distance, and performed departure volume data.

## Questions it answers
- What percentage of flights out of an airport are long-haul?
- How many long-haul departures does an airport have?
- What are the top long-haul destinations from an airport?

## Required fields
The loader requires:
- `origin`
- `distance_miles`
- `performed_departures`

It also uses `destination`, `year`, `month`, and `service_class` if available.

## How long-haul is defined
A flight is considered "long-haul" if its great-circle distance is greater than or equal to a configurable threshold (default 3,000 statute miles).

## How percentages are calculated
The percentage is calculated based on **performed departures**, not by counting rows or live flights. 
`percentage = (long_haul_departures / total_departures) * 100`

## Cargo/passenger caveat
By default, the calculation includes all reported T-100 performed departures (both passenger and cargo). If the dataset contains a `service_class` column, passenger-only filtering can be applied (Service Class F or G).

## Data freshness limitations
BTS T-100 data is not real-time. It is usually delayed by a few months. The metadata reflects the latest year and month available in the dataset.

## How to update the local dataset
1. Download the T-100 Segment (All Carriers) CSV or ZIP from the BTS TranStats website.
2. Place the file in `backend/data/raw/bts/`.
3. Restart the backend to reload the data.

*Note: The loader filters the dataset to only include origins in the supported peer set to save memory and speed up queries. It also builds a per-origin index so that chat queries only scan the relevant airport's data, not the full 300k+ row file.*