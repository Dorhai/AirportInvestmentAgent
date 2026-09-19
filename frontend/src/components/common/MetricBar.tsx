interface MetricBarProps {
  label: string;
  value: number | null;
  className?: string;
}

export function MetricBar({ label, value, className = "" }: MetricBarProps) {
  const pct = value != null ? Math.min(100, Math.max(0, value)) : 0;

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className="flex items-end justify-between font-mono text-xs uppercase">
        <span className="text-ink-muted">{label}</span>
        <span className="font-bold text-ink tracking-tight">
          {value != null ? value.toFixed(1) : "---"}
        </span>
      </div>
      <div className="h-1 w-full bg-paper border border-hairline relative">
        {value != null && (
          <div
            className="absolute top-0 left-0 h-full bg-ink transition-all duration-150"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}
