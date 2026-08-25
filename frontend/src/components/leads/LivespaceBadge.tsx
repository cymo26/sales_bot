import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Lead } from "@/lib/types";

type LivespaceBadgeLead = Pick<
  Lead,
  "livespace_sync_status" | "livespace_owner_name" | "livespace_deal_name" | "company_livespace_engaged" | "company_livespace_engaged_via"
>;

function personalLabel(owner: string | null, deal: string | null): string {
  if (owner && deal) return `Zajęty: ${owner} – ${deal}`;
  if (owner) return `Zajęty: ${owner}`;
  return `Aktywna szansa: ${deal}`;
}

/** Two independent warnings, never both for the same lead: a personal one
 * (this exact contact is owned in Livespace) takes priority; company_livespace_engaged
 * is computed backend-side to exclude the lead's own match, so it only ever
 * fires for a *different*, personally-unmatched contact at the same company.
 * "not_found" / "disabled" / never-synced render nothing — none of those is
 * a reason to interrupt a rep about to make contact. */
export function LivespaceBadge({ lead, className }: { lead: LivespaceBadgeLead; className?: string }) {
  if (lead.livespace_sync_status === "matched") {
    const label = personalLabel(lead.livespace_owner_name, lead.livespace_deal_name);
    return (
      <Badge variant="livespaceOwned" className={className} title={label}>
        {label}
      </Badge>
    );
  }
  if (lead.company_livespace_engaged) {
    const label = `Firma już obsługiwana: ${lead.company_livespace_engaged_via}`;
    return (
      <Badge variant="livespaceEngaged" className={className} title={label}>
        {label}
      </Badge>
    );
  }
  if (lead.livespace_sync_status === "error") {
    return (
      <span
        className="inline-flex items-center gap-1 text-[0.68rem] text-muted-foreground/60"
        title="Nie udało się sprawdzić statusu w Livespace"
      >
        <AlertTriangle className="h-3 w-3" />
        Livespace: błąd
      </span>
    );
  }
  return null;
}
