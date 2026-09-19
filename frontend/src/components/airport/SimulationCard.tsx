import type { SimulationBlock } from "@/types/chat";
import type { AirportScore } from "@/types/chat";
import { MetricBar } from "@/components/common/MetricBar";
import { formatAirportLabel } from "@/lib/airportDisplay";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";

type PresentOrAbsent = { kind: "present"; value: number } | { kind: "absent" };

function valueOf(field: PresentOrAbsent): number | null {
  return field.kind === "present" ? field.value : null;
}

function ScoreColumn({ label, score }: { label: string; score: AirportScore }) {
  return (
    <div className="flex-1 min-w-0">
      <p className="text-[10px] font-mono font-bold tracking-widest text-ink-muted uppercase border-b border-hairline pb-1">{label}</p>
      <div className="mt-2 flex flex-col">
        <p className="text-[10px] font-mono font-bold tracking-widest text-ink uppercase mb-1">Opportunity</p>
        <p className="text-xl font-bold font-mono text-ink tracking-tight">
          {valueOf(score.opportunity_score)?.toFixed(1) ?? "---"}
        </p>
      </div>
      <div className="mt-3 flex flex-col gap-2">
        <MetricBar label="Demand growth" value={valueOf(score.demand_growth_score)} />
        <MetricBar label="Congestion" value={valueOf(score.congestion_score)} />
        <MetricBar label="Delay pressure" value={valueOf(score.delay_pressure_score)} />
        <MetricBar label="Capacity pressure" value={valueOf(score.capacity_pressure_score)} />
      </div>
      <div className="mt-3">
        <ConfidenceBadge confidence={score.confidence} />
      </div>
    </div>
  );
}

export function SimulationCard({
  baseline,
  simulated,
  growthAdjustment,
  deltaOpportunity,
}: SimulationBlock) {
  return (
    <div className="border border-ink bg-white">
      <div className="border-b border-ink bg-ink text-white px-3 py-2 flex items-center justify-between">
        <h3 className="text-xs font-mono font-bold tracking-widest uppercase">
          Simulation: {formatAirportLabel(baseline.airport_code, baseline.airport_name)}
        </h3>
        <span className="text-[10px] font-mono border border-white/30 px-1 py-px">
          {growthAdjustment > 0 ? "+" : ""}
          {growthAdjustment}% GROWTH
        </span>
      </div>

      <div className="p-3">
        <div className="flex gap-4">
          <ScoreColumn label="Baseline" score={baseline} />
          <div className="w-px shrink-0 bg-hairline" />
          <ScoreColumn label="Simulated" score={simulated} />
        </div>

        {deltaOpportunity != null && (
          <div className="mt-4 border-t border-hairline pt-3 flex justify-between items-center bg-paper/50 p-2">
            <span className="text-xs font-mono font-bold text-ink-muted uppercase tracking-wider">
              Opportunity Delta
            </span>
            <span
              className={`font-bold font-mono text-base ${deltaOpportunity >= 0 ? "text-green" : "text-red"}`}
            >
              {deltaOpportunity >= 0 ? "+" : ""}
              {deltaOpportunity.toFixed(1)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
