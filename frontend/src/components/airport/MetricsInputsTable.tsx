import type { AirportMetrics } from "@/types/chat";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fmtDatum, fmtInt } from "@/lib/metricsDisplay";
import { formatAirportLabel } from "@/lib/airportDisplay";
import { METRICS_INPUT_COLUMNS } from "@/lib/evidenceTableLabels";

export interface MetricsInputsBlock {
  kind: "metrics_inputs";
  metricsList: AirportMetrics[];
}

export function MetricsInputsTable({ metricsList }: MetricsInputsBlock) {
  if (metricsList.length === 0) return null;

  return (
    <div className="border border-ink bg-white">
      <div className="border-b border-ink bg-ink text-white px-3 py-2">
        <h3 className="text-xs font-mono font-bold tracking-widest uppercase">
          Underlying Inputs
        </h3>
      </div>
      <div className="overflow-x-auto p-0">
        <Table className="font-mono text-xs">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {METRICS_INPUT_COLUMNS.map((col) => (
                <TableHead
                  key={col.label}
                  className={`whitespace-normal leading-tight ${col.align === "right" ? "text-right" : ""} text-muted-foreground ${col.className ?? ""}`}
                >
                  {col.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {metricsList.map((m) => (
              <TableRow key={m.airport_code} className="hover:bg-paper/50">
                <TableCell className="font-bold whitespace-normal leading-tight min-w-[8rem]">
                  {formatAirportLabel(m.airport_code, m.airport_name)}
                </TableCell>
                <TableCell className="text-right">{fmtInt(m.passenger_volume)}</TableCell>
                <TableCell className="text-right">{fmtInt(m.annual_operations)}</TableCell>
                <TableCell className="text-right">{fmtDatum(m.delayed_flights_pct)}%</TableCell>
                <TableCell className="text-right">{fmtDatum(m.average_delay_minutes)}</TableCell>
                <TableCell className="text-right">{fmtInt(m.long_haul_flights)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
