import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MultiSelect } from "@/components/ui/multi-select";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { leadsApi } from "@/lib/api";
import { AVAILABLE_TAGS, CANONICAL_STATUSES, STATUS_LABELS, type LeadFilters, type LeadStatus } from "@/lib/types";

/** "Oznacz leada" collapsible — mirrors tab_contacts.py's st.expander with the
 * bulk tag-assign and bulk status-change actions. Both act on every lead
 * matching the currently APPLIED filters, not just the rows on this page. */
interface BulkActionsPanelProps {
  total: number;
  filters: LeadFilters;
  onDone: () => void;
}

export function BulkActionsPanel({ total, filters, onDone }: BulkActionsPanelProps) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [tagsBusy, setTagsBusy] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [statusBusy, setStatusBusy] = useState(false);

  async function handleAssignTags() {
    if (tags.length === 0) return;
    setTagsBusy(true);
    try {
      const { updated } = await leadsApi.bulkTags(tags, filters);
      toast({
        title: "Tagi przypisane",
        description: `Tagi ${tags.slice().sort().join(", ")} przypisane do ${updated} leadów.`,
        variant: "success",
      });
      setTags([]);
      onDone();
    } catch {
      toast({ title: "Błąd", description: "Nie udało się przypisać tagów.", variant: "destructive" });
    } finally {
      setTagsBusy(false);
    }
  }

  async function handleChangeStatus() {
    if (!status) return;
    setStatusBusy(true);
    try {
      const { updated } = await leadsApi.bulkStatus(status, filters);
      toast({
        title: "Status zmieniony",
        description: `Status zmieniony na "${STATUS_LABELS[status as LeadStatus] ?? status}" dla ${updated} leadów.`,
        variant: "success",
      });
      setStatus("");
      onDone();
    } catch {
      toast({ title: "Błąd", description: "Nie udało się zmienić statusu.", variant: "destructive" });
    } finally {
      setStatusBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card/30">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-foreground"
        aria-expanded={open}
      >
        Oznacz leada
        <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-4 py-4">
          <p className="text-xs text-muted-foreground">
            Akcje dotyczą wszystkich przefiltrowanych leadów — obecnie <strong className="text-foreground">{total}</strong>.
          </p>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex-1">
              <MultiSelect
                options={[...AVAILABLE_TAGS]}
                value={tags}
                onChange={setTags}
                placeholder="Wybierz tagi do przypisania..."
              />
            </div>
            <Button onClick={handleAssignTags} disabled={tags.length === 0 || tagsBusy}>
              Przypisz tagi ({total})
            </Button>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex-1">
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger>
                  <SelectValue placeholder="Wybierz nowy status dla wszystkich..." />
                </SelectTrigger>
                <SelectContent>
                  {CANONICAL_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handleChangeStatus} disabled={!status || statusBusy}>
              Zmień status ({total})
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
