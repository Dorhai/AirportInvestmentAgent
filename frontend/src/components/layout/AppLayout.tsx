import type { ReactNode } from "react";

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-svh flex-col bg-paper text-ink">
      <header className="flex items-center justify-between border-b border-hairline px-6 py-4 bg-white">
        <div className="flex items-baseline gap-4">
          <h1 className="text-xl font-bold tracking-tight uppercase">AirportIQ</h1>
          <span className="text-sm font-mono text-ink-muted hidden sm:inline-block">ATFM Morning Briefing</span>
        </div>
        <div className="text-xs font-mono text-ink-muted text-right">
          <div>SYS STATUS: NOMINAL</div>
          <div>{new Date().toISOString().split('T')[0]}</div>
        </div>
      </header>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
