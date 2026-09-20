# Analyst capability matrix

Benchmark questions map to deterministic tools or explicit declines.

## New England expansion

| Question | Tool(s) | Notes |
|----------|---------|--------|
| Strong terminal expansion candidates | `rank_region(new_england)` | Opportunity score ranking |
| Factors for good candidates | `rank_region` or carried scores | Explain score components |
| Highest passenger growth | `rank_by_metric(passenger_growth)` | YoY from BTS T-100 origin (trailing window) |
| Close to terminal capacity | `rank_by_metric(capacity_pressure_score)` | Pax/ops proxy, not gates |
| Infrastructure constraints | `explain_capacity_pressure` | Proxy drivers only |
| Most benefit from gates | `rank_by_metric(capacity_pressure_score)` | Highest pressure in region |

## LAX vs SNA congestion

| Question | Tool(s) | Notes |
|----------|---------|--------|
| Compare congestion | `compare_airports` | Proxy congestion score |
| Main causes | `explain_congestion` | Ops, delays, pax weights |
| Peak hours/days | *(decline)* | Suggest delay pressure compare |
| Volume vs capacity split | *(decline)* | Suggest driver breakdown |
| More delay from congestion | `compare_airports` | Delay pressure in comparison |
| Trend over years | *(decline)* | Only YoY growth available |

## Anchorage long-haul

| Question | Tool(s) | Notes |
|----------|---------|--------|
| Long-haul percentage | `get_long_haul_percentage` | BTS T-100 performed departures |
| Destinations, airlines, season, cargo, underserved | *(decline)* | Coarse destination counts available from BTS; decline seasonality/underserved |

## SFO unmet demand

| Question | Tool(s) | Notes |
|----------|---------|--------|
| Unmet demand and why | `get_unmet_demand`, `get_airport_score` | Index + components |
| Why follow-up | `explain_unmet_demand` | Weighted drivers |
| Per-route, airlines, slots, flight count if constraint removed | *(decline)* | Index is aggregate proxy |

## Cross-cutting

| Question | Tool(s) | Notes |
|----------|---------|--------|
| Largest demand–capacity gap | `rank_by_metric(capacity_pressure_score)` | Peer universe |
| Value of one new route | *(decline)* | Suggest unmet demand rank |
| Passenger leakage | *(decline)* | Suggest peer compare |
| Capacity in 5–10 years | `rank_by_metric` or `simulate_airport_growth` | Scenario, not forecast |
