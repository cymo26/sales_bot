import * as React from "react";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiSelect } from "@/components/ui/multi-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { ApiError, companiesApi, conflictsFromError, leadsApi } from "@/lib/api";
import {
  ADD_NEW_INDUSTRY,
  AVAILABLE_TAGS,
  CANONICAL_STATUSES,
  STATUS_LABELS,
  type IndustryConflict,
  type LeadCreateInput,
  type LeadsCreateResult,
} from "@/lib/types";

const MAX_BLOCKS = 5;

interface LeadBlock {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  company: string;
  position: string;
  location: string;
  linkedin: string;
  industry: string;
  industryNew: string;
  status: string;
  tags: string[];
}

function makeBlock(): LeadBlock {
  return {
    id: crypto.randomUUID(),
    firstName: "",
    lastName: "",
    email: "",
    company: "",
    position: "",
    location: "",
    linkedin: "",
    industry: "",
    industryNew: "",
    status: CANONICAL_STATUSES[0],
    tags: [],
  };
}

function personLabel(n: number): string {
  if (n === 1) return "osobę";
  if (n >= 2 && n <= 4) return "osoby";
  return "osób";
}

function errorMessage(err: unknown): string | undefined {
  if (err instanceof ApiError) {
    const detail = (err.body as any)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const msgs = detail.map((d: any) => d?.msg).filter(Boolean);
      if (msgs.length > 0) return msgs.join(", ");
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return undefined;
}

export interface QuickAddModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function QuickAddModal({ open, onOpenChange, onCreated }: QuickAddModalProps) {
  const { toast } = useToast();

  const [blocks, setBlocks] = React.useState<LeadBlock[]>([makeBlock()]);
  const [industries, setIndustries] = React.useState<string[]>([]);
  const [errors, setErrors] = React.useState<string[]>([]);
  const [submitting, setSubmitting] = React.useState(false);

  const [conflicts, setConflicts] = React.useState<IndustryConflict[] | null>(null);
  const [pendingLeads, setPendingLeads] = React.useState<LeadCreateInput[] | null>(null);
  const [resolutions, setResolutions] = React.useState<Record<string, string>>({});

  // Fresh open → wipe everything (form blocks AND any stale conflict state).
  React.useEffect(() => {
    if (!open) return;
    setBlocks([makeBlock()]);
    setErrors([]);
    setConflicts(null);
    setPendingLeads(null);
    setResolutions({});
    companiesApi
      .industries()
      .then(setIndustries)
      .catch(() => setIndustries([]));
  }, [open]);

  function updateBlock(id: string, patch: Partial<LeadBlock>) {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  }

  function addBlock() {
    setBlocks((prev) => (prev.length >= MAX_BLOCKS ? prev : [...prev, makeBlock()]));
  }

  function removeBlock(id: string) {
    setBlocks((prev) => prev.filter((b) => b.id !== id));
  }

  function validateAndBuild(): { errors: string[]; leads: LeadCreateInput[] } {
    const validationErrors: string[] = [];
    const leads: LeadCreateInput[] = [];

    blocks.forEach((b, idx) => {
      const pos = idx + 1;

      let resolvedIndustry: string | null = null;
      if (b.industry === ADD_NEW_INDUSTRY) {
        const trimmed = b.industryNew.trim();
        if (!trimmed) {
          validationErrors.push(`Kontakt ${pos}: wpisz nazwę nowej branży lub wybierz istniejącą.`);
        } else {
          resolvedIndustry = trimmed;
        }
      } else if (b.industry) {
        resolvedIndustry = b.industry;
      }

      const missing: string[] = [];
      if (!b.firstName.trim()) missing.push("Imię");
      if (!b.lastName.trim()) missing.push("Nazwisko");
      if (!b.email.trim()) missing.push("Email");
      if (!b.company.trim()) missing.push("Firma");
      if (missing.length > 0) {
        validationErrors.push(`Kontakt ${pos}: brakuje — ${missing.join(", ")}`);
        return;
      }

      leads.push({
        first_name: b.firstName.trim(),
        last_name: b.lastName.trim(),
        email: b.email.trim(),
        company_name: b.company.trim(),
        company_industry: resolvedIndustry,
        position: b.position.trim() || null,
        location: b.location.trim() || null,
        linkedin_url: b.linkedin.trim() || null,
        status: b.status,
        tags: b.tags,
      });
    });

    return { errors: validationErrors, leads };
  }

  function handleSuccess(result: LeadsCreateResult) {
    let msg = `Dodano ${result.added} kontakt(ów) do bazy!`;
    if (result.skipped.length > 0) {
      msg += ` Pominięto ${result.skipped.length} duplikat(ów): ${result.skipped.join(", ")}`;
    }
    toast({ title: msg, variant: "success" });
    setBlocks([makeBlock()]);
    setErrors([]);
    setConflicts(null);
    setPendingLeads(null);
    setResolutions({});
    onOpenChange(false);
    onCreated();
  }

  async function handleSubmit() {
    const { errors: validationErrors, leads } = validateAndBuild();
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }
    setErrors([]);
    setSubmitting(true);
    try {
      const result = await leadsApi.create(leads, {});
      handleSuccess(result);
    } catch (err) {
      const conflictList = conflictsFromError(err);
      if (conflictList && conflictList.length > 0) {
        setPendingLeads(leads);
        setConflicts(conflictList);
        setResolutions({});
      } else {
        toast({
          variant: "destructive",
          title: "Nie udało się zapisać kontaktów",
          description: errorMessage(err),
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConflictConfirm() {
    if (!pendingLeads || !conflicts) return;
    setSubmitting(true);
    try {
      const finalResolutions: Record<string, string> = {};
      conflicts.forEach((c) => {
        finalResolutions[c.company] = resolutions[c.company] ?? "keep";
      });
      const result = await leadsApi.create(pendingLeads, finalResolutions);
      handleSuccess(result);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nie udało się zapisać kontaktów",
        description: errorMessage(err),
      });
    } finally {
      setSubmitting(false);
    }
  }

  function handleConflictBack() {
    setConflicts(null);
    setPendingLeads(null);
    setResolutions({});
  }

  const showBlockHeader = blocks.length > 1;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="large">
        <DialogHeader>
          <DialogTitle>Dodaj Nowe Kontakty</DialogTitle>
        </DialogHeader>

        {conflicts ? (
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-sm font-semibold">Wykryto konflikt branży</p>
              <p className="text-sm text-muted-foreground">
                Te firmy już istnieją w bazie z inną branżą. Zdecyduj dla każdej, czy zachować obecną wartość, czy
                nadpisać nową — nic nie zostało jeszcze zapisane.
              </p>
            </div>

            <div className="space-y-3">
              {conflicts.map((c) => {
                const choice = resolutions[c.company] ?? "keep";
                return (
                  <div key={c.company} className="rounded-md border border-border p-3">
                    <p className="mb-2 text-sm font-semibold">{c.company}</p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant={choice === "keep" ? "default" : "outline"}
                        onClick={() => setResolutions((r) => ({ ...r, [c.company]: "keep" }))}
                      >
                        Zachowaj obecną: „{c.current}”
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant={choice === "overwrite" ? "default" : "outline"}
                        onClick={() => setResolutions((r) => ({ ...r, [c.company]: "overwrite" }))}
                      >
                        Nadpisz na: „{c.incoming}”
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            <Separator />

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button className="flex-1" disabled={submitting} onClick={handleConflictConfirm}>
                Zatwierdź i zapisz
              </Button>
              <Button className="flex-1" variant="outline" disabled={submitting} onClick={handleConflictBack}>
                Wróć do formularza
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {blocks.map((b, idx) => (
              <React.Fragment key={b.id}>
                <div className="space-y-3">
                  {showBlockHeader && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wide text-muted-foreground/60">
                        Kontakt {idx + 1}
                      </span>
                      {idx > 0 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                          title="Usuń formularz"
                          onClick={() => removeBlock(b.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Imię *</Label>
                      <Input
                        placeholder="Jan"
                        value={b.firstName}
                        onChange={(e) => updateBlock(b.id, { firstName: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Nazwisko *</Label>
                      <Input
                        placeholder="Kowalski"
                        value={b.lastName}
                        onChange={(e) => updateBlock(b.id, { lastName: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Email *</Label>
                      <Input
                        placeholder="jan@firma.pl"
                        value={b.email}
                        onChange={(e) => updateBlock(b.id, { email: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Firma *</Label>
                      <Input
                        placeholder="Acme Sp. z o.o."
                        value={b.company}
                        onChange={(e) => updateBlock(b.id, { company: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Stanowisko</Label>
                      <Input
                        placeholder="CISO"
                        value={b.position}
                        onChange={(e) => updateBlock(b.id, { position: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Lokalizacja</Label>
                      <Input
                        placeholder="Warszawa"
                        value={b.location}
                        onChange={(e) => updateBlock(b.id, { location: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>LinkedIn URL</Label>
                      <Input
                        placeholder="https://linkedin.com/in/..."
                        value={b.linkedin}
                        onChange={(e) => updateBlock(b.id, { linkedin: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Branża firmy</Label>
                      <Select
                        value={b.industry || undefined}
                        onValueChange={(v) =>
                          updateBlock(b.id, {
                            industry: v,
                            industryNew: v === ADD_NEW_INDUSTRY ? b.industryNew : "",
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="— wybierz (opcjonalne) —" />
                        </SelectTrigger>
                        <SelectContent>
                          {industries.map((i) => (
                            <SelectItem key={i} value={i}>
                              {i}
                            </SelectItem>
                          ))}
                          <SelectItem value={ADD_NEW_INDUSTRY}>{ADD_NEW_INDUSTRY}</SelectItem>
                        </SelectContent>
                      </Select>
                      {b.industry === ADD_NEW_INDUSTRY && (
                        <Input
                          className="mt-2"
                          placeholder="np. GreenTech / Energy"
                          value={b.industryNew}
                          onChange={(e) => updateBlock(b.id, { industryNew: e.target.value })}
                        />
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Status</Label>
                      <Select value={b.status} onValueChange={(v) => updateBlock(b.id, { status: v })}>
                        <SelectTrigger>
                          <SelectValue />
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
                    <div className="space-y-1.5">
                      <Label>Tagi</Label>
                      <MultiSelect
                        options={[...AVAILABLE_TAGS]}
                        value={b.tags}
                        onChange={(next) => updateBlock(b.id, { tags: next })}
                        placeholder="Wybierz tagi..."
                      />
                    </div>
                  </div>
                </div>

                {idx < blocks.length - 1 && <Separator />}
              </React.Fragment>
            ))}

            <Separator />

            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" disabled={blocks.length >= MAX_BLOCKS} onClick={addBlock}>
                <Plus className="h-4 w-4" />
                Dodaj kolejną osobę
              </Button>
              {blocks.length >= MAX_BLOCKS && (
                <span className="text-xs text-muted-foreground">Osiągnięto limit {MAX_BLOCKS} kontaktów.</span>
              )}
            </div>

            {errors.length > 0 && (
              <div className="space-y-1 rounded-md border border-destructive/30 bg-destructive/5 p-3">
                {errors.map((e, i) => (
                  <p key={i} className="text-sm text-destructive">
                    {e}
                  </p>
                ))}
              </div>
            )}

            <Button className="w-full" disabled={submitting} onClick={handleSubmit}>
              {submitting
                ? "Zapisywanie…"
                : `Dodaj ${blocks.length} ${personLabel(blocks.length)} do bazy kontaktów`}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
