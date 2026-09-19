import type { ConfirmationBlock } from "@/types/chat";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface ConfirmationPromptProps extends ConfirmationBlock {
  onSelect?: (message: string) => void;
}

export function ConfirmationPrompt({
  confirmation,
  onSelect,
}: ConfirmationPromptProps) {
  return (
    <Alert className="rounded-none border-l-4 border-l-amber bg-amber/5">
      <AlertTitle className="font-mono text-xs font-bold uppercase tracking-wider text-amber">
        Awaiting Confirmation
      </AlertTitle>
      <AlertDescription className="space-y-4">
        <p className="text-sm text-foreground">{confirmation.prompt}</p>
        <div className="flex flex-wrap gap-2">
          {confirmation.options.map((opt) => (
            <Button
              key={opt.value}
              type="button"
              variant="outline"
              onClick={() => onSelect?.(opt.value)}
              className="rounded-none font-mono text-xs font-bold uppercase tracking-wider"
            >
              {opt.label}
            </Button>
          ))}
        </div>
      </AlertDescription>
    </Alert>
  );
}
