import type { ComparisonBlock } from "@/types/chat";
import { formatAirportLabel } from "@/lib/airportDisplay";
import { SCORE_TABLE_COLUMNS } from "@/lib/evidenceTableLabels";
import {
  COMPARISON_BADGE_HINTS,
  SCORE_METRIC_HINTS,
  type ScoreMetricHintKey,
} from "@/lib/scoreMetricHints";
import { MetricLabelHint } from "@/components/common/MetricLabelHint";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type PresentOrAbsent = { kind: "present"; value: number } | { kind: "absent" };

function fmt(field: PresentOrAbsent): string {
  return field.kind === "present" ? field.value.toFixed(1) : "---";
}

export function AirportComparison({
  rows,
  highestCongestion,
  highestOpportunity,
}: ComparisonBlock) {
  return (
    <div className="border border-ink bg-white">
      <div className="border-b border-ink bg-ink text-white px-3 py-2">
        <h3 className="text-xs font-mono font-bold tracking-widest uppercase">
          Comparison Matrix
        </h3>
      </div>
      <div className="overflow-x-auto p-0">
        <Table className="font-mono text-xs">
          <TableHeader className="overflow-visible">
            <TableRow className="hover:bg-transparent overflow-visible">
              <TableHead className="text-muted-foreground whitespace-normal leading-tight">Airport</TableHead>
              {SCORE_TABLE_COLUMNS.map((col) => (
                <TableHead
                  key={col.key}
                  className="text-muted-foreground whitespace-normal leading-tight text-right max-w-[4.5rem]"
                >
                  <MetricLabelHint
                    label={col.label}
                    description={SCORE_METRIC_HINTS[col.key as ScoreMetricHintKey]}
                    align="end"
                    side="bottom"
                    className="ml-auto"
                  />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const isTopOpp = row.airport_code === highestOpportunity;
              const isTopCong = row.airport_code === highestCongestion;
              return (
                <TableRow key={row.airport_code}>
                  <TableCell className="font-bold whitespace-normal leading-tight min-w-[8rem]">
                    {formatAirportLabel(row.airport_code, row.score.airport_name)}
                    {isTopOpp && (
                      <MetricLabelHint
                        label="TOP OPP"
                        description={COMPARISON_BADGE_HINTS.topOpp}
                        align="start"
                        underline={false}
                        className="ml-2 border border-green px-1 text-[9px] text-green"
                      />
                    )}
                    {isTopCong && (
                      <MetricLabelHint
                        label="MAX CONG"
                        description={COMPARISON_BADGE_HINTS.maxCong}
                        align="start"
                        underline={false}
                        className="ml-2 border border-amber px-1 text-[9px] text-amber"
                      />
                    )}
                  </TableCell>
                  <TableCell
                    className={`text-right ${isTopOpp ? "font-bold text-green" : ""}`}
                  >
                    {fmt(row.score.opportunity_score)}
                  </TableCell>
                  <TableCell className="text-right">{fmt(row.score.demand_growth_score)}</TableCell>
                  <TableCell
                    className={`text-right ${isTopCong ? "font-bold text-amber" : ""}`}
                  >
                    {fmt(row.score.congestion_score)}
                  </TableCell>
                  <TableCell className="text-right">{fmt(row.score.delay_pressure_score)}</TableCell>
                  <TableCell className="text-right">{fmt(row.score.capacity_pressure_score)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <div className="bg-paper/30 px-3 py-1.5 border-t border-hairline">
        <p className="text-[10px] font-mono text-ink-muted uppercase">
          * Component scores are normalized 0–100 vs peers
        </p>
      </div>
    </div>
  );
}
