import type { components } from "./api.generated";

export type ChatResponse = components["schemas"]["ChatResponse"];
export type AirportScore = components["schemas"]["AirportScore"];
export type AirportMetrics = components["schemas"]["AirportMetrics"];
export type ComparisonRow = components["schemas"]["ComparisonRow"];
export type Confirmation = components["schemas"]["Confirmation"];

export type EvidenceItem = ChatResponse["evidence"][number];

export type TextBlock = { kind: "text"; text: string };
export type ScoreCardBlock = { kind: "score_card"; score: AirportScore };
export type ComparisonBlock = {
  kind: "comparison";
  rows: ComparisonRow[];
  highestCongestion: string | null;
  highestOpportunity: string | null;
};
export type RankingBlock = {
  kind: "ranking";
  ranked: AirportScore[];
  region: string;
  peerNote: string;
  metric: string;
};
export type SimulationBlock = {
  kind: "simulation";
  baseline: AirportScore;
  simulated: AirportScore;
  growthAdjustment: number;
  deltaOpportunity: number | null;
};
export type KpiBlock = {
  kind: "kpi";
  label: string;
  datum: components["schemas"]["Present_float_"] | components["schemas"]["Absent"];
};
export type ConfirmationBlock = {
  kind: "confirmation";
  confirmation: Confirmation;
};
export type WarningsBlock = { kind: "warnings"; warnings: string[] };

export type MetricsInputsBlock = {
  kind: "metrics_inputs";
  metricsList: AirportMetrics[];
};

export type ComponentBreakdownBlock = {
  kind: "component_breakdown";
  scores: AirportScore[];
};

export type MethodologyBlock = {
  kind: "methodology";
};

export type Block =
  | TextBlock
  | ScoreCardBlock
  | ComparisonBlock
  | RankingBlock
  | SimulationBlock
  | KpiBlock
  | ConfirmationBlock
  | WarningsBlock
  | MetricsInputsBlock
  | ComponentBreakdownBlock
  | MethodologyBlock;

export interface Turn {
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}
