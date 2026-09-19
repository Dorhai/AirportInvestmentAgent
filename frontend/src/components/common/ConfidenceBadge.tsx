import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ConfidenceBadgeProps {
  confidence: "HIGH" | "MEDIUM" | "LOW";
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const styles =
    confidence === "HIGH"
      ? "border-green text-green bg-green/10"
      : confidence === "MEDIUM"
        ? "border-amber text-amber bg-amber/10"
        : "border-red text-red bg-red/10";

  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-none font-mono text-[10px] font-bold tracking-widest uppercase px-1 py-px",
        styles,
      )}
      aria-label={`Score confidence: ${confidence.toLowerCase()}`}
    >
      {confidence}
    </Badge>
  );
}
