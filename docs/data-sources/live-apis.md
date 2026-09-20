# Data sources

AirportIQ combines **live HTTP APIs** with **optional local BTS bulk CSVs** you place under `backend/data/`. Configure paths in the repository root `.env` (paths are relative to `backend/` when the API runs).

## Live HTTP APIs

### 1. NTAD Aviation Facilities
- **Endpoint:** `https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Aviation_Facilities/FeatureServer/0/query`
- **Purpose:** Airport catalog (coordinates, names) and facility context (acreage, part 139 class, tower type).
- **Query shape:** ArcGIS REST query with `where ICAO_ID IN (...)` and specific `outFields`.

### 2. BTS T-100 Segment Summary by Origin
- **Endpoint:** `https://data.bts.gov/resource/r495-tyji.json`
- **Purpose:** Per-airport monthly passenger and departure data.
- **Query shape:** Socrata SoQL filtering by `origin_airport_code`, ordered by `reporting_month`.
- **Aggregation:** Trailing window (`BTS_TRAILING_MONTHS`, default 12) vs previous window for YoY-style metrics.
- **Optional:** `BTS_APP_ID` Socrata app token for higher rate limits.

### 3. BTS National AFF T-100 Summary
- **Endpoint:** `https://data.bts.gov/resource/jqx4-4iha.json`
- **Purpose:** National monthly totals for context (passengers, departures, load factor).
- **Aggregation:** Same trailing-window pattern as origin summary.

### 4. NOAA Aviation Weather
- **Endpoint:** `https://aviationweather.gov/api/data/metar`
- **Purpose:** Live METAR (flight category, wind, visibility). Gated by `WEATHER_ENABLED`.
- **Query shape:** Batched `ids=KBOS,KJFK,...` with `format=json`.

### 5. FAA NAS Status
- **Endpoint:** `https://nasstatus.faa.gov/api/airport-status-information`
- **Purpose:** Active ground delay programs and ground stops (congestion bump when GDP active).

## Optional local bulk files

### 6. BTS On-Time Performance (CSV)
- **Config:** `BTS_ONTIME_CSV_PATH` or `BTS_ONTIME_DATA_DIR`
- **Example file:** `backend/data/T_ONTIME_REPORTING.csv`
- **Purpose:** Departure delay percentages, average delay minutes, delay causes.
- **Load:** In memory at startup when configured; scoring uses a trailing window on departure delays.

### 7. BTS T-100 Segment (CSV)
- **Config:** `BTS_T100_SEGMENT_PATH`
- **Example file:** `backend/data/T_T100_SEGMENT_ALL_CARRIER.csv`
- **Purpose:** Segment-level departures and distance for **long-haul percentage** and route summaries.
- **Load:** In memory at startup when configured.

Large CSVs are typically gitignored (`backend/data/*`); ship sample paths in `.env.example` and document download sources for reviewers.

## What these sources cannot supply

- **Per-segment distance from live T-100 origin API alone** — use the segment bulk file for long-haul %.
- **Peak hour / day congestion** — annual and trailing-window proxies only.
- **Financial ROI or gate-level terminal capacity** — operational public-data proxies only.
