import { type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import {
  Collapsible as CollapsibleRoot,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface CollapsibleProps {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function Collapsible({ title, children, defaultOpen = false }: CollapsibleProps) {
  return (
    <CollapsibleRoot defaultOpen={defaultOpen} className="border-t border-hairline py-2">
      <CollapsibleTrigger className="flex w-full items-center justify-between text-xs font-mono font-medium text-ink hover:text-ink-muted transition-colors uppercase tracking-wider">
        <span>{title}</span>
        <ChevronDown className="size-3.5 shrink-0 transition-transform duration-100 [[data-state=open]_&]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent
        className={cn(
          "mt-2 text-sm text-ink-muted leading-relaxed font-sans",
          "border-l-2 border-hairline pl-3 py-1 bg-muted/30",
        )}
      >
        {children}
      </CollapsibleContent>
    </CollapsibleRoot>
  );
}
