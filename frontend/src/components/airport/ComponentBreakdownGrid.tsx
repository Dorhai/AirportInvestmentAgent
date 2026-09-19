import type { AirportScore } from "@/types/chat";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatAirportLabel } from "@/lib/airportDisplay";
import { MetricBar } from "@/components/common/MetricBar";
import { MetricLabelHint } from "@/components/common/MetricLabelHint";
import { SCORE_METRIC_HINTS } from "@/lib/scoreMetricHints";

const COMPONENT_ROWS: { key: keyof typeof SCORE_METRIC_HINTS; label: string }[] = [
  { key: "demand", label: "Demand Growth" },
  { key: "congestion", label: "Congestion" },
  { key: "delay", label: "Delay Pressure" },
  { key: "capacity", label: "Capacity Pressure" },
];

export interface ComponentBreakdownBlock {
  kind: "component_breakdown";
  scores: AirportScore[];
}

function valueOf(field: { kind: "present"; value: number } | { kind: "absent" }): number | null {
  return field.kind === "present" ? field.value : null;
}

export function ComponentBreakdownGrid({ scores }: ComponentBreakdownBlock) {
  if (scores.length < 2) return null;

  return (
    <div className="border border-ink bg-white mt-2">
      <div className="border-b border-ink bg-paper/50 px-3 py-1">
        <h4 className="text-[10px] font-mono font-bold tracking-widest uppercase text-ink-muted">
          Score Components (0-100)
        </h4>
      </div>
      <div className="p-0">
        <Table className="font-mono text-xs">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="text-muted-foreground min-w-[7rem] whitespace-normal">
                Component
              </TableHead>
              {scores.map((s) => (
                <TableHead
                  key={s.airport_code}
                  className="text-center font-bold whitespace-normal leading-tight min-w-[5rem]"
                >
                  {formatAirportLabel(s.airport_code, s.airport_name)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {COMPONENT_ROWS.map((row, rowIndex) => (
              <TableRow
                key={row.key}
                className={`hover:bg-transparent ${rowIndex === COMPONENT_ROWS.length - 1 ? "border-b-0" : ""}`}
              >
                <TableCell className="relative z-10 whitespace-normal text-ink-muted">
                  <MetricLabelHint
                    label={row.label}
                    description={SCORE_METRIC_HINTS[row.key]}
                    align="start"
                    side="bottom"
                  />
                </TableCell>
                {scores.map((s) => {
                  const value =
                    row.key === "demand"
                      ? valueOf(s.demand_growth_score)
                      : row.key === "congestion"
                        ? valueOf(s.congestion_score)
                        : row.key === "delay"
                          ? valueOf(s.delay_pressure_score)
                          : valueOf(s.capacity_pressure_score);
                  return (
                    <TableCell key={s.airport_code} className="align-bottom pb-3">
                      <MetricBar label="" value={value} className="gap-0" />
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
