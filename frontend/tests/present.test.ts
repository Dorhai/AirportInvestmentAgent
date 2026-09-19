import { describe, it, expect } from "vitest";
import { presentResponse } from "@/services/present";
import type { ChatResponse } from "@/types/chat";

function sampleOrigin() {
  return {
    kind: "sample" as const,
    source: "sample_airports.json",
    period: "2023",
    citation: "FAA T-100",
  };
}

function presentFloat(value: number) {
  return { kind: "present" as const, value, origin: sampleOrigin() };
}

function makeScore() {
  return {
    airport_code: "BOS" as const,
    opportunity_score: presentFloat(72.5),
    demand_growth_score: presentFloat(65.0),
    congestion_score: presentFloat(80.0),
    delay_pressure_score: presentFloat(55.0),
    capacity_pressure_score: presentFloat(70.0),
    confidence: "MEDIUM" as const,
    snapshot_at: "2024-01-01T00:00:00Z",
    assumptions: ["Growth rate based on historical trends"],
    limitations: ["Sample data only"],
    sources: ["FAA T-100"],
  };
}

function baseChatResponse(
  overrides: Partial<ChatResponse> = {},
): ChatResponse {
  return {
    message: "",
    airports: [],
    analysis_type: null,
    scores: {},
    sources: [],
    assumptions: [],
    warnings: [],
    confidence: "LOW",
    data_freshness: "sample",
    evidence: [],
    evidence_origin: "none",
    needs_confirmation: null,
    ...overrides,
  };
}

describe("presentResponse", () => {
  it("maps a ScoreResult into text, score_card and methodology blocks", () => {
    const response = baseChatResponse({
      message: "Here is the BOS analysis",
      airports: ["BOS"],
      warnings: ["Sample data used"],
      evidence: [
        {
          kind: "score",
          airports: ["BOS"],
          snapshot_at: "2024-01-01T00:00:00Z",
          score: makeScore(),
        },
      ],
    });

    const blocks = presentResponse(response);

    expect(blocks).toHaveLength(3);
    expect(blocks[0]).toEqual({
      kind: "text",
      text: "Here is the BOS analysis",
    });
    expect(blocks[1]).toMatchObject({
      kind: "score_card",
      score: { airport_code: "BOS", confidence: "MEDIUM" },
    });
    expect(blocks[2]).toEqual({
      kind: "methodology",
    });
  });

  it("returns only a text block when there is no evidence", () => {
    const response = baseChatResponse({ message: "Hello" });
    const blocks = presentResponse(response);
    expect(blocks).toEqual([{ kind: "text", text: "Hello" }]);
  });

  it("returns a confirmation block and stops before evidence", () => {
    const response = baseChatResponse({
      message: "Which airport?",
      needs_confirmation: {
        prompt: "Did you mean BOS or BDL?",
        options: [
          { label: "BOS", value: "BOS" },
          { label: "BDL", value: "BDL" },
        ],
      },
      evidence: [
        {
          kind: "score",
          airports: ["BOS"],
          snapshot_at: "2024-01-01T00:00:00Z",
          score: makeScore(),
        },
      ],
    });

    const blocks = presentResponse(response);

    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toMatchObject({ kind: "text" });
    expect(blocks[1]).toMatchObject({ kind: "confirmation" });
  });

  it("includes metrics but skips rejection evidence items", () => {
    const response = baseChatResponse({
      message: "Info",
      evidence: [
        {
          kind: "metrics",
          airports: ["BOS"],
          snapshot_at: "2024-01-01T00:00:00Z",
          metrics: {
            airport_code: "BOS",
            passenger_volume: presentFloat(30_000_000),
            previous_passenger_volume: presentFloat(28_000_000),
            annual_operations: presentFloat(400_000),
            delayed_flights_pct: presentFloat(18.5),
            average_delay_minutes: presentFloat(22.3),
            long_haul_flights: presentFloat(5000),
            total_departures: presentFloat(200_000),
            sources: ["FAA"],
            data_period: "2023",
            completeness_score: 0.85,
            freshness: "sample",
          },
        },
        {
          kind: "rejection",
          airports: ["BOS"],
          snapshot_at: "2024-01-01T00:00:00Z",
          tool_name: "simulate",
          reason: "not allowed",
        },
      ],
    });

    const blocks = presentResponse(response);

    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toMatchObject({ kind: "text" });
    expect(blocks[1]).toMatchObject({ kind: "metrics_inputs" });
  });

  it("ranking and comparison omit component grid and methodology", () => {
    const response = baseChatResponse({
      message: "Ranked list",
      evidence: [
        {
          kind: "ranking",
          airports: ["BOS", "PVD"],
          snapshot_at: "2024-01-01T00:00:00Z",
          ranked: [makeScore(), { ...makeScore(), airport_code: "PVD" }],
          region: "new_england",
          peer_note: "Ranked by opportunity_score",
          metric: "opportunity_score",
        },
      ],
    });
    const blocks = presentResponse(response);
    expect(blocks.some((b) => b.kind === "component_breakdown")).toBe(false);
    expect(blocks.some((b) => b.kind === "methodology")).toBe(false);
    expect(blocks.some((b) => b.kind === "ranking")).toBe(true);
  });

  it("does not render KPI cards for long_haul evidence", () => {
    const response = baseChatResponse({
      message: "Long-haul summary",
      evidence: [
        {
          kind: "long_haul",
          airports: ["LAX"],
          snapshot_at: "2024-01-01T00:00:00Z",
          long_haul_pct: presentFloat(13.2),
        },
      ],
    });

    const blocks = presentResponse(response);
    expect(blocks).toEqual([{ kind: "text", text: "Long-haul summary" }]);
    expect(blocks.some((b) => b.kind === "kpi")).toBe(false);
  });

  it("does not render KPI cards for unmet_demand evidence", () => {
    const response = baseChatResponse({
      message: "Unmet demand summary",
      evidence: [
        {
          kind: "unmet_demand",
          airports: ["BOS"],
          snapshot_at: "2024-01-01T00:00:00Z",
          unmet_demand_index: presentFloat(48.5),
        },
        {
          kind: "unmet_demand",
          airports: ["BDL"],
          snapshot_at: "2024-01-01T00:00:00Z",
          unmet_demand_index: presentFloat(37.3),
        },
      ],
    });

    const blocks = presentResponse(response);
    expect(blocks).toEqual([{ kind: "text", text: "Unmet demand summary" }]);
    expect(blocks.some((b) => b.kind === "kpi")).toBe(false);
  });

  it("merges consecutive metrics items into one block", () => {
    const response = baseChatResponse({
      evidence: [
        {
          kind: "metrics",
          airports: ["BOS"],
          snapshot_at: "2024-01-01T00:00:00Z",
          metrics: {
            airport_code: "BOS",
            passenger_volume: presentFloat(30_000_000),
            previous_passenger_volume: presentFloat(28_000_000),
            annual_operations: presentFloat(400_000),
            delayed_flights_pct: presentFloat(18.5),
            average_delay_minutes: presentFloat(22.3),
            long_haul_flights: presentFloat(5000),
            total_departures: presentFloat(200_000),
            sources: ["FAA"],
            data_period: "2023",
            completeness_score: 0.85,
            freshness: "sample",
          },
        },
        {
          kind: "metrics",
          airports: ["LAX"],
          snapshot_at: "2024-01-01T00:00:00Z",
          metrics: {
            airport_code: "LAX",
            passenger_volume: presentFloat(40_000_000),
            previous_passenger_volume: presentFloat(38_000_000),
            annual_operations: presentFloat(500_000),
            delayed_flights_pct: presentFloat(15.5),
            average_delay_minutes: presentFloat(12.3),
            long_haul_flights: presentFloat(8000),
            total_departures: presentFloat(250_000),
            sources: ["FAA"],
            data_period: "2023",
            completeness_score: 0.95,
            freshness: "sample",
          },
        },
      ],
    });

    const blocks = presentResponse(response);
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ kind: "metrics_inputs" });
    expect((blocks[0] as any).metricsList).toHaveLength(2);
  });
});
