/** Display-only copy for score table labels (not used in calculations). */

export const SCORE_METRIC_HINTS = {
  opportunity:
    "Weighted expansion signal from demand, congestion, delay, and capacity components. Scored 0–100 vs peer airports; higher suggests stronger opportunity.",
  demand:
    "Year-over-year passenger growth, normalized to 0–100 against the peer set. Higher means faster rising demand.",
  congestion:
    "Operational congestion proxy from flight volume, delay share, and passengers. Normalized 0–100 vs peers; higher means busier / more constrained.",
  delay:
    "Delay stress from the share of delayed flights and average delay minutes. Normalized 0–100; higher means worse on-time performance.",
  capacity:
    "Capacity tightness from passengers per operation (and growth when available). Normalized 0–100 vs peers; higher means heavier utilization pressure.",
  confidence:
    "How complete and reliable the underlying core KPIs and score components are. HIGH, MEDIUM, or LOW — not a performance score.",
} as const;

export type ScoreMetricHintKey = keyof typeof SCORE_METRIC_HINTS;

export const COMPARISON_BADGE_HINTS = {
  topOpp: "Highest opportunity score in this comparison.",
  maxCong: "Highest congestion score in this comparison.",
} as const;
