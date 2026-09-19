import type { KpiBlock } from "@/types/chat";

export function KpiCard({ label, datum }: KpiBlock) {
  const isPresent = datum.kind === "present";
  const display = isPresent ? datum.value.toFixed(1) : "---";
  const detail = !isPresent ? datum.detail : null;

  return (
    <div className="border border-hairline bg-white p-3 flex justify-between items-end gap-4 shadow-sm">
      <div className="flex flex-col gap-1">
        <p className="text-[10px] font-mono font-bold tracking-widest text-ink-muted uppercase">
          {label}
        </p>
        {detail && (
          <p className="text-[9px] font-mono text-ink-muted border-l-2 border-hairline pl-1">
            {detail}
          </p>
        )}
      </div>
      <p className="text-2xl font-bold font-mono text-ink leading-none tracking-tight">
        {display}
      </p>
    </div>
  );
}
