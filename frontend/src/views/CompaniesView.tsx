import { useEffect, useState } from "react";

import { PageLayout, SidebarSection } from "@/components/layout/Sidebar";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MultiSelect } from "@/components/ui/multi-select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { LeadListHeader, LeadListRow } from "@/components/leads/LeadList";
import { Pagination } from "@/components/leads/Pagination";
import { useToast } from "@/hooks/use-toast";
import { companiesApi } from "@/lib/api";
import { AVAILABLE_TAGS, type CompaniesPage } from "@/lib/types";
import type { CompanyNavRequest } from "@/lib/nav";

interface CompaniesViewProps {
  onOpenLead: (leadId: string) => void;
  navRequest: CompanyNavRequest | null;
  refreshSignal: number;
}

interface CompanyFilters {
  search: string;
  locations: string[];
  tags: string[];
}

const EMPTY_COMPANY_FILTERS: CompanyFilters = { search: "", locations: [], tags: [] };
const EMPTY_PAGE: CompaniesPage = { rows: [], meta: { page: 1, pages: 1, total: 0 } };

function hasActiveFilters(f: CompanyFilters): boolean {
  return f.search !== "" || f.locations.length > 0 || f.tags.length > 0;
}

/** "Baza Firm" — account-based, company-level view. React port of
 * ui/tabs/tab_companies.py: staged sidebar filters (search / location / tag),
 * a company-level Accordion whose bodies render the shared LeadList rows
 * (already tag-filtered server-side), and cross-tab navigation from the Lead
 * Detail modal's "Przejdź do profilu firmy" (props.navRequest) that pre-fills
 * the search filter and auto-expands the target company once its page loads. */
export function CompaniesView({ onOpenLead, navRequest, refreshSignal }: CompaniesViewProps) {
  const { toast } = useToast();

  const [draft, setDraft] = useState<CompanyFilters>(EMPTY_COMPANY_FILTERS);
  const [applied, setApplied] = useState<CompanyFilters>(EMPTY_COMPANY_FILTERS);
  const [page, setPage] = useState(1);

  const [locationOptions, setLocationOptions] = useState<string[]>([]);
  const [pageData, setPageData] = useState<CompaniesPage>(EMPTY_PAGE);
  const [loading, setLoading] = useState(true);

  const [expanded, setExpanded] = useState<string[]>([]);
  const [pendingExpandId, setPendingExpandId] = useState<string | null>(null);

  // ── Location filter options — fetched once. ──
  useEffect(() => {
    let cancelled = false;
    companiesApi
      .locations()
      .then((locs) => {
        if (!cancelled) setLocationOptions(locs);
      })
      .catch(() => {
        if (!cancelled) {
          toast({ title: "Błąd", description: "Nie udało się pobrać lokalizacji.", variant: "destructive" });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Cross-tab navigation: pre-fill search with the target company's name,
  // clear other filters, and remember its id to auto-expand once loaded. ──
  useEffect(() => {
    if (!navRequest) return;
    const next: CompanyFilters = { search: navRequest.companyName, locations: [], tags: [] };
    setDraft(next);
    setApplied(next);
    setPage(1);
    setPendingExpandId(navRequest.companyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navRequest?.nonce]);

  // ── Data: one page of companies with nested (tag-filtered) leads. ──
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    companiesApi
      .list(page, applied.search, applied.locations, applied.tags)
      .then((res) => {
        if (cancelled) return;
        setPageData(res);
      })
      .catch(() => {
        if (!cancelled) {
          toast({ title: "Błąd", description: "Błąd przy pobieraniu firm.", variant: "destructive" });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, applied, refreshSignal]);

  // ── One-shot auto-expand once the target company's page has arrived. ──
  useEffect(() => {
    if (!pendingExpandId) return;
    if (pageData.rows.some((c) => c.id === pendingExpandId)) {
      setExpanded((prev) => (prev.includes(pendingExpandId) ? prev : [...prev, pendingExpandId]));
      setPendingExpandId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageData]);

  function handleSaveFilters() {
    setApplied(draft);
    setPage(1);
  }

  function handleClearFilters() {
    setDraft(EMPTY_COMPANY_FILTERS);
    setApplied(EMPTY_COMPANY_FILTERS);
    setPage(1);
  }

  const activeFilters = hasActiveFilters(applied);

  const sidebar = (
    <>
      <SidebarSection title="Szukaj po nazwie firmy">
        <Input
          value={draft.search}
          onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
          placeholder="np. Acme, Comarch..."
        />
      </SidebarSection>

      <SidebarSection title="Lokalizacja">
        <MultiSelect
          options={locationOptions}
          value={draft.locations}
          onChange={(v) => setDraft((d) => ({ ...d, locations: v }))}
          placeholder="Lokalizacja"
        />
      </SidebarSection>

      <SidebarSection title="Filtruj po tagu">
        <MultiSelect
          options={[...AVAILABLE_TAGS]}
          value={draft.tags}
          onChange={(v) => setDraft((d) => ({ ...d, tags: v }))}
          placeholder="Filtruj po tagu"
        />
      </SidebarSection>

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
    <PageLayout sidebar={sidebar}>
      <h1 className="text-2xl font-semibold text-foreground">Baza Firm (Account-Based View)</h1>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      ) : pageData.rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          {activeFilters ? "Brak firm pasujących do filtrów." : "Brak firm w bazie danych."}
        </div>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            Znaleziono <span className="font-semibold text-foreground">{pageData.meta.total}</span> firm(y).
          </p>

          <Accordion type="multiple" value={expanded} onValueChange={setExpanded} className="space-y-2">
            {pageData.rows.map((company) => (
              <AccordionItem key={company.id} value={company.id}>
                <AccordionTrigger>
                  <span className="truncate">
                    {company.name} — {company.domain ?? "—"} · {company.leads.length} kontakt(ów)
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="mb-3 grid grid-cols-1 gap-2 text-sm text-foreground/85 sm:grid-cols-3">
                    <div>
                      <span className="font-semibold text-foreground">Branża:</span> {company.industry ?? "—"}
                    </div>
                    <div>
                      <span className="font-semibold text-foreground">Lokalizacja:</span> {company.location ?? "—"}
                    </div>
                    <div>
                      <span className="font-semibold text-foreground">Wielkość:</span> {company.size_range ?? "—"}
                    </div>
                  </div>

                  {company.leads.length > 0 ? (
                    <div>
                      <LeadListHeader />
                      <div className="divide-y divide-border/50">
                        {company.leads.map((lead) => (
                          <LeadListRow key={lead.id} lead={lead} onOpenDetail={onOpenLead} />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">Brak kontaktów pasujących do filtrów.</p>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </>
      )}

      <Pagination meta={pageData.meta} onPageChange={setPage} noun="firm" />
    </PageLayout>
  );
}
