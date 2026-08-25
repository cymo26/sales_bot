import { Linkedin } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { LivespaceBadge } from "@/components/leads/LivespaceBadge";
import { StatusBadge } from "@/components/leads/StatusBadge";
import { TagPills } from "@/components/leads/TagPills";
import { display, fullName } from "@/lib/utils";
import type { Lead } from "@/lib/types";

/** Shared lead list primitives — the React equivalent of ui/components.py's
 * render_lead_table_header() / render_lead_row(), used by BOTH the Kontakty
 * list (with the bulk-delete checkbox column) and the nested lead lists
 * inside each company card on the Baza Firm tab (without it). Column
 * proportions mirror the original _LEAD_WEIGHTS exactly so both call sites
 * stay visually aligned. */

const BASE_COLS = "2fr 2.3fr 1.8fr 2fr 1.3fr 1fr 1.5fr 1.6fr 0.8fr auto";
const CHECKBOX_COL = "1.75rem";

function gridCols(withCheckbox: boolean) {
  return withCheckbox ? `${CHECKBOX_COL} ${BASE_COLS}` : BASE_COLS;
}

function TruncatedCell({ value, bold, mono }: { value: string; bold?: boolean; mono?: boolean }) {
  return (
    <div
      title={value}
      className={`truncate-cell ${bold ? "font-semibold text-foreground" : "text-foreground/85"} ${mono ? "font-mono text-[0.82rem] text-muted-foreground" : ""}`}
    >
      {value}
    </div>
  );
}

interface LeadListHeaderProps {
  withCheckbox?: boolean;
  allChecked?: boolean;
  onToggleAll?: (checked: boolean) => void;
}

export function LeadListHeader({ withCheckbox, allChecked, onToggleAll }: LeadListHeaderProps) {
  return (
    <div
      className="grid items-center gap-3 border-b border-border px-3 pb-2 text-[0.68rem] font-bold uppercase tracking-wider text-muted-foreground/55"
      style={{ gridTemplateColumns: gridCols(!!withCheckbox) }}
    >
      {withCheckbox && (
        <Checkbox checked={!!allChecked} onCheckedChange={(c) => onToggleAll?.(c === true)} aria-label="Zaznacz wszystkie" />
      )}
      <div>Imię i Nazwisko</div>
      <div>Email</div>
      <div>Firma</div>
      <div>Stanowisko</div>
      <div>Lokalizacja</div>
      <div>Status</div>
      <div>Tagi</div>
      <div>Livespace</div>
      <div>LN</div>
      <div />
    </div>
  );
}

interface LeadListRowProps {
  lead: Lead;
  withCheckbox?: boolean;
  checked?: boolean;
  onToggleChecked?: (checked: boolean) => void;
  onOpenDetail: (leadId: string) => void;
}

export function LeadListRow({ lead, withCheckbox, checked, onToggleChecked, onOpenDetail }: LeadListRowProps) {
  return (
    <div
      className="group grid items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-accent/40"
      style={{ gridTemplateColumns: gridCols(!!withCheckbox) }}
    >
      {withCheckbox && (
        <Checkbox checked={!!checked} onCheckedChange={(c) => onToggleChecked?.(c === true)} aria-label={`Zaznacz ${fullName(lead.first_name, lead.last_name, lead.email)}`} />
      )}
      <TruncatedCell value={fullName(lead.first_name, lead.last_name, lead.email)} bold />
      <TruncatedCell value={display(lead.email)} mono />
      <TruncatedCell value={display(lead.company_name)} />
      <TruncatedCell value={display(lead.position)} />
      <TruncatedCell value={display(lead.location)} />
      <div>
        <StatusBadge status={lead.status} />
      </div>
      <TagPills tags={lead.tags} />
      <div className="min-w-0">
        <LivespaceBadge lead={lead} className="max-w-full truncate" />
      </div>
      <div>
        {lead.linkedin_url ? (
          <a
            href={lead.linkedin_url}
            target="_blank"
            rel="noreferrer"
            title="Profil LinkedIn"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-primary/30 bg-primary/5 text-primary transition-colors hover:bg-primary/15 hover:text-primary"
          >
            <Linkedin className="h-3.5 w-3.5" />
          </a>
        ) : (
          <span className="text-sm text-muted-foreground/30">—</span>
        )}
      </div>
      <div>
        <Button variant="outline" size="sm" className="h-7 px-2.5 text-xs" onClick={() => onOpenDetail(lead.id)}>
          Szczegóły
        </Button>
      </div>
    </div>
  );
}
