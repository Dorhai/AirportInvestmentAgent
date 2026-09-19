import { Badge } from "@/components/ui/badge";

interface SourceBadgeProps {
  source: string;
}

export function SourceBadge({ source }: SourceBadgeProps) {
  return (
    <Badge
      variant="secondary"
      className="rounded-none bg-muted font-mono text-[10px] text-muted-foreground uppercase"
    >
      {source}
    </Badge>
  );
}
