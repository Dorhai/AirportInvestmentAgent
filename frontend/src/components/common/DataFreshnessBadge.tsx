import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface DataFreshnessBadgeProps {
  freshness: "live" | "sample" | "mixed";
}

const labels: Record<string, string> = {
  sample: "SIMULATED / SAMPLE",
  mixed: "CACHED / MIXED",
};

export function DataFreshnessBadge({ freshness }: DataFreshnessBadgeProps) {
  if (freshness === "live") return null;

  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-none border-amber bg-amber/10 text-[10px] font-mono font-bold text-amber whitespace-nowrap",
      )}
    >
      {labels[freshness] ?? freshness.toUpperCase()}
    </Badge>
  );
}
