import type { AirportScore, AirportMetrics } from "@/types/chat";

const live = { kind: "live" as const, source: "FAA", period: "2025-Q1", fetched_at: "2025-04-01" };

export function present(value: number) {
  return { kind: "present" as const, value, origin: live };
}

export function presentInt(value: number) {
  return { kind: "present" as const, value, origin: live };
}

export function mockAirportScore(
  overrides: Partial<AirportScore> = {},
): AirportScore {
  return {
    airport_code: "BOS",
    airport_name: "General Edward Lawrence Logan International Airport",
    opportunity_score: present(72.4),
    demand_growth_score: present(65.0),
    congestion_score: present(58.2),
    delay_pressure_score: present(44.1),
    capacity_pressure_score: present(51.3),
    confidence: "HIGH",
    snapshot_at: "2026-03-19T12:00:00Z",
    assumptions: ["Peer universe only"],
    limitations: ["Sample delay data"],
    sources: ["FAA", "OpenSky"],
    ...overrides,
  };
}

export function mockAirportMetrics(
  overrides: Partial<AirportMetrics> = {},
): AirportMetrics {
  return {
    airport_code: "BOS",
    airport_name: "General Edward Lawrence Logan International Airport",
    passenger_volume: presentInt(20_000_000),
    previous_passenger_volume: presentInt(18_000_000),
    annual_operations: presentInt(200_000),
    delayed_flights_pct: present(22.0),
    average_delay_minutes: present(18.0),
    long_haul_flights: presentInt(5000),
    total_departures: presentInt(100_000),
    sources: ["FAA", "BTS"],
    data_period: "2025-Q1",
    completeness_score: 1.0,
    freshness: "mixed",
    ...overrides,
  };
}
