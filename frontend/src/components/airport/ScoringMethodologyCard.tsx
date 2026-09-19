import { useEffect, useState } from "react";
import { getScoringMethodology } from "@/services/api";
import type { components } from "@/types/api.generated";
import { Collapsible } from "@/components/common/Collapsible";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type ScoringMethodology = components["schemas"]["ScoringMethodology"];

export interface MethodologyBlock {
  kind: "methodology";
}

export function ScoringMethodologyCard(_props: MethodologyBlock) {
  const [data, setData] = useState<ScoringMethodology | null>(null);
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    getScoringMethodology()
      .then(setData)
      .catch(() => setError(true));
  }, []);

  if (error) return null;
  if (!data) return null;

  return (
    <div className="border border-ink bg-white">
      <Collapsible title="Scoring methodology (deterministic)" defaultOpen={false}>
        <div className="p-3 bg-paper/30">
          <Table className="font-mono text-xs mb-4">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-muted-foreground w-1/2">Component</TableHead>
                <TableHead className="text-right text-muted-foreground w-1/2">Weight</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(data.weights).map(([key, weight]) => (
                <TableRow key={key} className="hover:bg-transparent">
                  <TableCell className="font-bold">
                    {data.component_labels[key] ?? key}
                  </TableCell>
                  <TableCell className="text-right text-green font-bold">
                    {Math.round(weight * 100)}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div>
            <h4 className="text-[10px] font-mono font-bold tracking-widest uppercase text-ink-muted mb-2">
              Rules & Context
            </h4>
            <ul className="list-inside list-disc text-xs font-mono space-y-1 text-ink">
              {data.rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ul>
          </div>
        </div>
      </Collapsible>
    </div>
  );
}
