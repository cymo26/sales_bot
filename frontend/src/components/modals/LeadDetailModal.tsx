import * as React from "react";
import { Building2, Linkedin, RefreshCw } from "lucide-react";

import { LivespaceBadge } from "@/components/leads/LivespaceBadge";
import { StatusBadge } from "@/components/leads/StatusBadge";
import { TagPills } from "@/components/leads/TagPills";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { ApiError, leadsApi } from "@/lib/api";
import { CANONICAL_STATUSES, STATUS_LABELS, type LeadDetail, type LeadStatus } from "@/lib/types";
import { display, fullName } from "@/lib/utils";

export interface LeadDetailModalProps {
  leadId: string | null;
  onOpenChange: (open: boolean) => void;
  onGoToCompany: (companyId: string, companyName: string) => void;
  onMutated: () => void;
}

function errorMessage(err: unknown): string | undefined {
  if (err instanceof ApiError) {
    const detail = (err.body as any)?.detail;
    if (typeof detail === "string") return detail;
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return undefined;
}

function DetailField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground/70">{label}</p>
      <div className="text-sm text-foreground">{value}</div>
    </div>
  );
}

export function LeadDetailModal({ leadId, onOpenChange, onGoToCompany, onMutated }: LeadDetailModalProps) {
  const { toast } = useToast();

  const [lead, setLead] = React.useState<LeadDetail | null>(null);
  const [loading, setLoading] = React.useState(false);

  const [status, setStatus] = React.useState<string>(CANONICAL_STATUSES[0]);
  const [notes, setNotes] = React.useState<string>("");

  const [saving, setSaving] = React.useState(false);
  const [confirmingDelete, setConfirmingDelete] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [refreshingLivespace, setRefreshingLivespace] = React.useState(false);

  React.useEffect(() => {
    if (leadId === null) return;
    let cancelled = false;
    setLoading(true);
    setLead(null);
    setConfirmingDelete(false);
    leadsApi
      .get(leadId)
      .then((detail) => {
        if (cancelled) return;
        setLead(detail);
        setStatus(detail.status);
        setNotes(detail.notes ?? "");
      })
      .catch(() => {
        if (cancelled) return;
        toast({ variant: "destructive", title: "Nie znaleziono kontaktu." });
        onOpenChange(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leadId]);

  async function handleSave() {
    if (!leadId) return;
    setSaving(true);
    try {
      const result = await leadsApi.update(leadId, status, notes.trim() === "" ? null : notes);
      toast({ title: result.changed ? "Zmiany zapisane!" : "Brak zmian do zapisania." });
      if (result.changed) onMutated();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nie udało się zapisać zmian",
        description: errorMessage(err),
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleRefreshLivespace() {
    if (!leadId) return;
    setRefreshingLivespace(true);
    try {
      const result = await leadsApi.refreshLivespace(leadId);
      setLead((prev) => (prev ? { ...prev, ...result } : prev));
      if (result.livespace_sync_status === "matched") {
        toast({ title: "Kontakt jest już obsługiwany w Livespace.", variant: "destructive" });
      } else if (result.livespace_sync_status === "not_found") {
        toast({ title: "Nie znaleziono w Livespace — kontakt wygląda na wolny." });
      } else if (result.livespace_sync_status === "disabled") {
        toast({ title: "Integracja z Livespace nie jest skonfigurowana." });
      } else if (result.livespace_sync_status === "error") {
        toast({ variant: "destructive", title: "Nie udało się sprawdzić statusu w Livespace." });
      }
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nie udało się odświeżyć statusu Livespace",
        description: errorMessage(err),
      });
    } finally {
      setRefreshingLivespace(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!leadId) return;
    setDeleting(true);
    try {
      await leadsApi.delete(leadId);
      toast({ title: "Kontakt usunięty." });
      onOpenChange(false);
      onMutated();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nie udało się usunąć kontaktu",
        description: errorMessage(err),
      });
    } finally {
      setDeleting(false);
      setConfirmingDelete(false);
    }
  }

  return (
    <Dialog open={leadId !== null} onOpenChange={onOpenChange}>
      <DialogContent size="large">
        <DialogHeader>
          <DialogTitle>Profil Kontaktu</DialogTitle>
        </DialogHeader>

        {loading || !lead ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-9 w-28" />
            </div>
            <Skeleton className="h-4 w-64" />
            <Separator />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {/* Header */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <h3 className="text-lg font-semibold leading-none tracking-tight">
                  {fullName(lead.first_name, lead.last_name, lead.email)}
                </h3>
                {lead.linkedin_url && (
                  <Button asChild variant="outline" size="sm">
                    <a href={lead.linkedin_url} target="_blank" rel="noreferrer">
                      <Linkedin className="h-4 w-4" />
                      LinkedIn
                    </a>
                  </Button>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                {display(lead.position)}&nbsp;&nbsp;·&nbsp;&nbsp;{display(lead.company_name)}
              </p>
              {lead.tags.length > 0 && <TagPills tags={lead.tags} />}
              <div className="flex flex-wrap items-center gap-2">
                <LivespaceBadge lead={lead} />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 gap-1 px-2 text-xs text-muted-foreground"
                  disabled={refreshingLivespace}
                  onClick={handleRefreshLivespace}
                >
                  <RefreshCw className={`h-3 w-3 ${refreshingLivespace ? "animate-spin" : ""}`} />
                  Odśwież status Livespace
                </Button>
              </div>
            </div>

            <Separator />

            {/* Details */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <DetailField label="Email" value={display(lead.email)} />
              <div className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground/70">Firma</p>
                <p className="text-sm text-foreground">{display(lead.company_name)}</p>
                {lead.company_id && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-1"
                    onClick={() => onGoToCompany(lead.company_id as string, lead.company_name ?? "")}
                  >
                    <Building2 className="h-4 w-4" />
                    Przejdź do profilu firmy
                  </Button>
                )}
              </div>
              <DetailField label="Lokalizacja" value={display(lead.location)} />
              <DetailField label="Status" value={<StatusBadge status={lead.status} />} />
              <DetailField label="Branża firmy" value={lead.industry ?? "—"} />
              <DetailField label="Wielkość firmy" value={lead.size_range ?? "—"} />
            </div>

            <Separator />

            {/* Editable section */}
            <div className="space-y-3">
              <p className="text-sm font-semibold">Edytuj rekord</p>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Status</Label>
                  <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CANONICAL_STATUSES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {STATUS_LABELS[s as LeadStatus]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label>Notatki</Label>
                <Textarea
                  value={notes}
                  maxLength={500}
                  placeholder="Wpisz swoje notatki operacyjne…"
                  className="min-h-[120px]"
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            </div>

            <Separator />

            {/* Footer */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button disabled={saving} onClick={handleSave}>
                {saving ? "Zapisywanie…" : "Zapisz zmiany"}
              </Button>

              {confirmingDelete ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-foreground">Na pewno usunąć?</span>
                  <Button variant="destructive" size="sm" disabled={deleting} onClick={handleDeleteConfirm}>
                    {deleting ? "Usuwanie…" : "Tak, usuń"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={deleting}
                    onClick={() => setConfirmingDelete(false)}
                  >
                    Anuluj
                  </Button>
                </div>
              ) : (
                <Button variant="destructive" onClick={() => setConfirmingDelete(true)}>
                  Usuń kontakt
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
