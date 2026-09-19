import type { WarningsBlock } from "@/types/chat";
import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function WarningsList({ warnings }: WarningsBlock) {
  if (warnings.length === 0) return null;

  return (
    <Alert variant="destructive" className="rounded-none border-l-4 border-l-destructive bg-destructive/5">
      <AlertTriangle className="size-4" />
      <AlertTitle className="font-mono text-[10px] font-bold tracking-widest uppercase">
        System Warnings
      </AlertTitle>
      <AlertDescription>
        <ul className="flex flex-col gap-1.5">
          {warnings.map((w, i) => (
            <li key={i} className="flex items-start gap-2 font-mono text-xs text-muted-foreground">
              <span className="text-destructive/50">-</span>
              <span className="leading-snug">{w}</span>
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
