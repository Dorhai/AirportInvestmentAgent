import type { RankingBlock, AirportScore } from "@/types/chat";
import { formatAirportLabel } from "@/lib/airportDisplay";
import { rankingMetricLabel, RANKING_DISPLAY_LIMIT } from "@/lib/rankingMetricLabels";

type PresentOrAbsent = { kind: "present"; value: number } | { kind: "absent" };

function fmt(field: PresentOrAbsent): string {
  return field.kind === "present" ? field.value.toFixed(1) : "---";
}

const METRIC_ON_SCORE: Record<string, keyof AirportScore> = {
  opportunity_score: "opportunity_score",
  demand_growth_score: "demand_growth_score",
  congestion_score: "congestion_score",
  delay_pressure_score: "delay_pressure_score",
  capacity_pressure_score: "capacity_pressure_score",
  passenger_growth: "demand_growth_score",
};

function rankedValue(score: AirportScore, metric: string): PresentOrAbsent {
  const key = METRIC_ON_SCORE[metric] ?? "opportunity_score";
  const field = score[key];
  if (field && typeof field === "object" && "kind" in field) {
    return field as PresentOrAbsent;
  }
  return score.opportunity_score;
}

export function RankingTable({ ranked, region, metric }: RankingBlock) {
  const metricName = rankingMetricLabel(metric);
  const subtitle =
    ranked.length > RANKING_DISPLAY_LIMIT
      ? `Top ${RANKING_DISPLAY_LIMIT} of ${ranked.length} airports · ranked by ${metricName}`
      : `Ranked by ${metricName} · ${ranked.length} airports`;

  const displayRanked = ranked.slice(0, RANKING_DISPLAY_LIMIT);

  return (
    <div className="border border-ink bg-white">
      <div className="border-b border-ink bg-ink text-white px-3 py-2">
        <h3 className="text-xs font-mono font-bold tracking-widest uppercase">
          {region.replace(/_/g, " ")} Ranking
        </h3>
      </div>
      <div className="p-3">
        <p className="mb-3 text-xs font-mono font-semibold text-ink normal-case border-l-2 border-ink pl-2 py-1">
          {subtitle}
        </p>

        <div className="mb-1 flex justify-end pr-3 text-[10px] font-mono font-semibold uppercase tracking-wide text-ink/70">
          {metricName}
        </div>

        <ol className="flex flex-col gap-1">
          {displayRanked.map((score, i) => (
            <li
              key={score.airport_code}
              className="flex items-center gap-3 border border-hairline px-3 py-2.5 bg-white hover:bg-paper/50 hover:border-ink/30 transition-colors"
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center bg-ink text-white text-[10px] font-mono font-bold">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 font-semibold text-ink font-mono text-sm leading-snug">
                {formatAirportLabel(score.airport_code, score.airport_name)}
              </span>
              <span className="shrink-0 text-sm font-mono font-bold tabular-nums text-green">
                {fmt(rankedValue(score, metric))}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
