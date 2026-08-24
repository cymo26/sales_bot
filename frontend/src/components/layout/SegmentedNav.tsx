import { Building2, Upload, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import type { TabKey } from "@/lib/nav";

const TABS: { key: TabKey; label: string; icon: typeof Users }[] = [
  { key: "kontakty", label: "Kontakty", icon: Users },
  { key: "firmy", label: "Baza Firm", icon: Building2 },
  { key: "import", label: "Import Danych (CSV)", icon: Upload },
];

interface SegmentedNavProps {
  value: TabKey;
  onChange: (tab: TabKey) => void;
}

/** Mirrors dashboard.py's st.segmented_control navigation — same three
 * destinations, same order. Icons replace the emoji glyphs the Streamlit
 * labels used, per the "no emojis, professional SaaS look" requirement. */
export function SegmentedNav({ value, onChange }: SegmentedNavProps) {
  return (
    <nav className="inline-flex items-center gap-1 rounded-lg border border-border bg-secondary/40 p-1">
      {TABS.map(({ key, label, icon: Icon }) => {
        const active = value === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={cn(
              "flex items-center gap-2 rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors",
              active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        );
      })}
    </nav>
  );
}
