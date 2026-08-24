import type { ReactNode } from "react";

import { SegmentedNav } from "@/components/layout/SegmentedNav";
import type { TabKey } from "@/lib/nav";

interface AppShellProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  children: ReactNode;
}

export function AppShell({ activeTab, onTabChange, children }: AppShellProps) {
  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex shrink-0 flex-col gap-4 border-b border-border px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold tracking-tight">SALES BOT</h1>
        <SegmentedNav value={activeTab} onChange={onTabChange} />
      </header>
      <div className="flex flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
