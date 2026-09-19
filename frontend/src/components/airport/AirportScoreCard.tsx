import type { ScoreCardBlock } from "@/types/chat";
import { MetricBar } from "@/components/common/MetricBar";
import { SourceBadge } from "@/components/common/SourceBadge";
import { Collapsible } from "@/components/common/Collapsible";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatAirportLabel } from "@/lib/airportDisplay";
import { cn } from "@/lib/utils";

import { AirportContextBanner } from "./AirportContextBanner";

type PresentOrAbsent = { kind: "present"; value: number } | { kind: "absent" };

function valueOf(field: PresentOrAbsent): number | null {
  return field.kind === "present" ? field.value : null;
}

export function AirportScoreCard({ score }: ScoreCardBlock) {
  const opportunity = valueOf(score.opportunity_score);

  return (
    <Card className={cn("gap-0 rounded-none py-0 shadow-none ring-1 ring-foreground/20")}>
      <CardHeader className="flex-row items-center border-b border-border bg-background px-3 py-2 text-foreground">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-bold leading-snug font-mono sm:text-base">
            {formatAirportLabel(score.airport_code, score.airport_name)}
          </h3>
          <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
            {new Date(score.snapshot_at).toISOString().split("T")[0]}
          </span>
        </div>
      </CardHeader>

      <CardContent className="p-3">
        <AirportContextBanner context={score.context} />
        
        <div className="mb-4">
          <div className="mb-1 flex items-end gap-2">
            <span className="text-3xl font-bold font-mono text-green leading-none tracking-tight">
              {opportunity != null ? opportunity.toFixed(1) : "---"}
            </span>
            <span className="mb-1 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              OPPORTUNITY SCORE
            </span>
          </div>
          <div className="h-1 w-full border border-border bg-muted relative mt-1">
            {opportunity != null && (
              <div
                className="absolute top-0 left-0 h-full bg-primary transition-all duration-150"
                style={{ width: `${Math.min(100, Math.max(0, opportunity))}%` }}
              />
            )}
          </div>
        </div>

        <div className="grid gap-3 border-t border-border pt-3">
          <MetricBar label="Demand Growth" value={valueOf(score.demand_growth_score)} />
          <MetricBar label="Congestion" value={valueOf(score.congestion_score)} />
          <MetricBar label="Delay Pressure" value={valueOf(score.delay_pressure_score)} />
          <MetricBar label="Capacity Pressure" value={valueOf(score.capacity_pressure_score)} />
        </div>

        <div className="mt-4 flex flex-col gap-0 border-t border-border pt-2">
          {score.assumptions.length > 0 && (
            <Collapsible title={`Assumptions [${score.assumptions.length}]`}>
              <ul className="list-inside list-disc">
                {score.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </Collapsible>
          )}

          {score.limitations.length > 0 && (
            <Collapsible title={`Limitations [${score.limitations.length}]`}>
              <ul className="list-inside list-disc">
                {score.limitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </Collapsible>
          )}

          {score.sources.length > 0 && (
            <Collapsible title={`Sources [${score.sources.length}]`}>
              <div className="flex flex-wrap gap-1">
                {score.sources.map((s) => (
                  <SourceBadge key={s} source={s} />
                ))}
              </div>
            </Collapsible>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
