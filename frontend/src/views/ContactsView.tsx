import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, Plus, Trash2 } from "lucide-react";

import { BulkActionsPanel } from "@/components/leads/BulkActionsPanel";
import { LeadListHeader, LeadListRow } from "@/components/leads/LeadList";
import { Pagination } from "@/components/leads/Pagination";
import { PageLayout, SidebarSection } from "@/components/layout/Sidebar";
import { QuickAddModal } from "@/components/modals/QuickAddModal";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { MultiSelect } from "@/components/ui/multi-select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { downloadBlob, leadsApi } from "@/lib/api";
import {
  AVAILABLE_TAGS,
  EMPTY_FILTERS,
  STATUS_LABELS,
  type LeadFilterOptions,
  type LeadFilters,
  type LeadMetrics,
  type LeadsPage,
  type LeadStatus,
} from "@/lib/types";

interface ContactsViewProps {
  onOpenLead: (leadId: string) => void;
  refreshSignal: number;
  onMutated: () => void;
}

const EMPTY_OPTIONS: LeadFilterOptions = { locations: [], positions: [], statuses: [], companies: [] };
const EMPTY_METRICS: LeadMetrics = { total: 0, new: 0, companies: 0, with_position: 0 };
const EMPTY_PAGE: LeadsPage = { rows: [], meta: { page: 1, pages: 1, total: 0 } };

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-card/40 px-4 py-3">
      <div className="text-[0.68rem] font-bold uppercase tracking-wide text-muted-foreground/60">{label}</div>
      <div className="mt-1 text-2xl font-bold text-foreground">{value}</div>
    </div>
  );
}

function hasActiveFilters(f: LeadFilters): boolean {
  return (
    f.search !== "" ||
    f.companies.length > 0 ||
    f.locations.length > 0 ||
    f.statuses.length > 0 ||
    f.positions.length > 0 ||
    f.tags.length > 0 ||
    f.email_only ||
    f.no_email
  );
}

/** "Twoje Kontakty" — staged filters + summary metrics + bulk actions + CSV
 * export + the paginated lead table. React port of ui/tabs/tab_contacts.py:
 * filters are edited in a local "draft" and only take effect (query the
 * backend, reset to page 1) on "Zapisz filtry", mirroring the original's
 * session_state-staged filter bar without the rerun plumbing. */
export function ContactsView({ onOpenLead, refreshSignal, onMutated }: ContactsViewProps) {
  const { toast } = useToast();

  const [draft, setDraft] = useState<LeadFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<LeadFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  const [options, setOptions] = useState<LeadFilterOptions>(EMPTY_OPTIONS);
  const [metrics, setMetrics] = useState<LeadMetrics>(EMPTY_METRICS);
  const [pageData, setPageData] = useState<LeadsPage>(EMPTY_PAGE);
  const [listLoading, setListLoading] = useState(true);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);

  // ── Filter options (cascading, server-side) — re-fetch whenever the
  // APPLIED filters change. Tags are a static local constant. ──
  useEffect(() => {
    let cancelled = false;
    leadsApi
      .filterOptions(applied)
      .then((opts) => {
        if (!cancelled) setOptions(opts);
      })
      .catch(() => {
        if (!cancelled) {
          toast({ title: "Błąd", description: "Nie udało się pobrać opcji filtrów.", variant: "destructive" });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied]);

  // ── Metrics + current page of rows ──
  const refetch = useCallback(async () => {
    setListLoading(true);
    try {
      const [metricsRes, listRes] = await Promise.all([leadsApi.metrics(applied), leadsApi.list(page, applied)]);
      setMetrics(metricsRes);
      setPageData(listRes);
    } catch {
      toast({ title: "Błąd", description: "Błąd przy pobieraniu danych.", variant: "destructive" });
    } finally {
      setListLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, applied]);

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refetch, refreshSignal]);

  // ── Selection guard: a stale selection from a previous page/filter can't
  // silently carry over and delete the wrong rows. ──
  const visibleIdsKey = useMemo(() => pageData.rows.map((r) => r.id).join(","), [pageData]);
  useEffect(() => {
    setSelectedIds(new Set());
  }, [visibleIdsKey]);

  async function afterMutation() {
    await refetch();
    onMutated();
  }

  function handleSaveFilters() {
    setApplied(draft);
    setPage(1);
  }

  function handleClearFilters() {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPage(1);
  }

  function toggleRow(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(pageData.rows.map((r) => r.id)) : new Set());
  }

  async function handleBulkDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setDeleteBusy(true);
    try {
      const { deleted } = await leadsApi.bulkDelete(ids);
      toast({ title: "Usunięto", description: `Usunięto ${deleted} kontakt(ów).`, variant: "success" });
      setSelectedIds(new Set());
      await afterMutation();
    } catch {
      toast({ title: "Błąd", description: "Nie udało się usunąć kontaktów.", variant: "destructive" });
    } finally {
      setDeleteBusy(false);
    }
  }

  async function handleExport() {
    setExportBusy(true);
    try {
      const blob = await leadsApi.exportCsv(applied);
      downloadBlob(blob, "apple_script_outreach.csv");
    } catch {
      toast({ title: "Błąd", description: "Eksport nie powiódł się.", variant: "destructive" });
    } finally {
      setExportBusy(false);
    }
  }

  async function handleCreated() {
    await afterMutation();
  }

  const allChecked = pageData.rows.length > 0 && pageData.rows.every((r) => selectedIds.has(r.id));
  const activeFilters = hasActiveFilters(applied);

  const statusOptions = options.statuses.map((s) => ({ value: s, label: STATUS_LABELS[s as LeadStatus] ?? s }));

  const activeFilterChips: string[] = [];
  if (applied.search) activeFilterChips.push(`Szukaj: ${applied.search}`);
  if (applied.companies.length) activeFilterChips.push(`Firma: ${applied.companies.join(", ")}`);
  if (applied.locations.length) activeFilterChips.push(`Lokalizacja: ${applied.locations.join(", ")}`);
  if (applied.statuses.length)
    activeFilterChips.push(`Status: ${applied.statuses.map((s) => STATUS_LABELS[s as LeadStatus] ?? s).join(", ")}`);
  if (applied.positions.length) activeFilterChips.push(`Stanowisko: ${applied.positions.join(", ")}`);
  if (applied.tags.length) activeFilterChips.push(`Tagi: ${applied.tags.join(", ")}`);
  if (applied.email_only) activeFilterChips.push("Tylko z emailem: TAK");
  if (applied.no_email) activeFilterChips.push("Tylko bez emaila: TAK");

  const sidebar = (
    <>
      <SidebarSection title="Szukaj">
        <Input
          value={draft.search}
          onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
          placeholder="Imię, nazwisko, email..."
        />
      </SidebarSection>

      <SidebarSection title="Firma">
        <MultiSelect
          options={options.companies}
          value={draft.companies}
          onChange={(v) => setDraft((d) => ({ ...d, companies: v }))}
          placeholder="Firma"
        />
      </SidebarSection>

      <SidebarSection title="Lokalizacja">
        <MultiSelect
          options={options.locations}
          value={draft.locations}
          onChange={(v) => setDraft((d) => ({ ...d, locations: v }))}
          placeholder="Lokalizacja"
        />
      </SidebarSection>

      <SidebarSection title="Stanowisko">
        <MultiSelect
          options={options.positions}
          value={draft.positions}
          onChange={(v) => setDraft((d) => ({ ...d, positions: v }))}
          placeholder="Stanowisko"
        />
      </SidebarSection>

      <SidebarSection title="Status">
        <MultiSelect
          options={statusOptions}
          value={draft.statuses}
          onChange={(v) => setDraft((d) => ({ ...d, statuses: v }))}
          placeholder="Status"
        />
      </SidebarSection>

      <SidebarSection title="Tagi">
        <MultiSelect
          options={[...AVAILABLE_TAGS]}
          value={draft.tags}
          onChange={(v) => setDraft((d) => ({ ...d, tags: v }))}
          placeholder="Tagi"
        />
      </SidebarSection>

      <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground/85">
        <Checkbox
          checked={draft.email_only}
          onCheckedChange={(c) =>
            setDraft((d) => ({ ...d, email_only: c === true, no_email: c === true ? false : d.no_email }))
          }
        />
        Tylko z emailem
      </label>

      <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground/85">
        <Checkbox
          checked={draft.no_email}
          onCheckedChange={(c) =>
            setDraft((d) => ({ ...d, no_email: c === true, email_only: c === true ? false : d.email_only }))
          }
        />
        Tylko bez emaila
      </label>

      <Separator />

      <div className="flex flex-col gap-2">
        <Button onClick={handleSaveFilters}>Zapisz filtry</Button>
        <Button variant="outline" onClick={handleClearFilters}>
          Wyczyść filtry
        </Button>
      </div>
    </>
  );

  return (
    <>
      <PageLayout sidebar={sidebar}>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold text-foreground">Twoje Kontakty</h1>
          <div className="flex items-center gap-2">
            <Button onClick={() => setQuickAddOpen(true)}>
              <Plus /> Dodaj leada
            </Button>
            <Button
              variant="destructive"
              disabled={selectedIds.size === 0 || deleteBusy}
              onClick={handleBulkDelete}
            >
              <Trash2 /> Usuń zaznaczone ({selectedIds.size})
            </Button>
          </div>
        </div>

        {activeFilterChips.length > 0 && (
          <p className="text-xs text-muted-foreground">Aktywne filtry: {activeFilterChips.join(" | ")}</p>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Łącznie" value={metrics.total} />
          <StatTile label="Nowe" value={metrics.new} />
          <StatTile label="Firmy" value={metrics.companies} />
          <StatTile label="Ze stanowiskiem" value={metrics.with_position} />
        </div>

        <div className="flex justify-end">
          <Button variant="outline" disabled={metrics.total === 0 || exportBusy} onClick={handleExport}>
            <Download /> Eksportuj CSV ({metrics.total})
          </Button>
        </div>

        <BulkActionsPanel total={metrics.total} filters={applied} onDone={afterMutation} />

        {listLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-11 w-full rounded-lg" />
            ))}
          </div>
        ) : pageData.rows.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            {activeFilters
              ? "Brak wyników dla aktualnych filtrów. Zmień kryteria lub wyczyść filtry."
              : 'Brak leadów w bazie danych. Zaimportuj dane w zakładce "Import".'}
          </div>
        ) : (
          <div>
            <LeadListHeader withCheckbox allChecked={allChecked} onToggleAll={toggleAll} />
            <div className="divide-y divide-border/50">
              {pageData.rows.map((lead) => (
                <LeadListRow
                  key={lead.id}
                  lead={lead}
                  withCheckbox
                  checked={selectedIds.has(lead.id)}
                  onToggleChecked={(c) => toggleRow(lead.id, c)}
                  onOpenDetail={onOpenLead}
                />
              ))}
            </div>
          </div>
        )}

        <Pagination meta={pageData.meta} onPageChange={setPage} noun="kontaktów" />
      </PageLayout>

      <QuickAddModal open={quickAddOpen} onOpenChange={setQuickAddOpen} onCreated={handleCreated} />
    </>
  );
}
