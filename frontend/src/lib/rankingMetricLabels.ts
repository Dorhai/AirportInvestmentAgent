/** Display labels for rank_by_metric / ranking peer notes (not API field names). */

const LABELS: Record<string, string> = {
  opportunity_score: "opportunity score",
  demand_growth_score: "demand growth score",
  congestion_score: "congestion score",
  delay_pressure_score: "delay pressure score",
  capacity_pressure_score: "capacity pressure score",
  passenger_growth: "passenger growth",
  unmet_demand_index: "unmet demand index",
};

export const RANKING_DISPLAY_LIMIT = 4;

export function rankingMetricLabel(metric: string): string {
  return LABELS[metric] ?? metric.replace(/_/g, " ");
}
