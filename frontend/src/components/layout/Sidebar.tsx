import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

/** Pure layout primitive — the persistent left filter rail. Feature views
 * (ContactsView, CompaniesView) render their own filter controls as
 * children; this component only owns the chrome. */
export function Sidebar({ children }: { children: ReactNode }) {
  return (
    <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-card/30 px-4 py-5">
      <div className="space-y-5">{children}</div>
    </aside>
  );
}

export function SidebarSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{title}</Label>
      {children}
    </div>
  );
}

/** The two-pane body under the header: optional sidebar + scrollable main
 * content. Used by every tab view, including Import which omits `sidebar`. */
export function PageLayout({ sidebar, children }: { sidebar?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-1 overflow-hidden">
      {sidebar && <Sidebar>{sidebar}</Sidebar>}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-6xl space-y-5">{children}</div>
      </main>
    </div>
  );
}
