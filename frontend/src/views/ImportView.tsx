import * as React from "react";
import { AlertTriangle, CheckCircle2, FileText, Info, UploadCloud, X, XCircle } from "lucide-react";

import { PageLayout } from "@/components/layout/Sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiSelect } from "@/components/ui/multi-select";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { ApiError, companiesApi, importApi } from "@/lib/api";
import { ADD_NEW_INDUSTRY, AVAILABLE_TAGS, type ImportResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_FILES = 5;

interface SelectedFile {
  id: string;
  file: File;
  /** null while the client-side preview read is still in flight. */
  lineCount: number | null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Display-only stand-in for the original's pandas df preview: line count
 * minus the header row, minus trailing blank lines. Not a CSV parser — good
 * enough for "about how many rows is this". */
function countRows(text: string): number {
  const lines = text.split(/\r\n|\r|\n/);
  while (lines.length > 0 && lines[lines.length - 1].trim() === "") lines.pop();
  return Math.max(lines.length - 1, 0);
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

export interface ImportViewProps {
  onImported: () => void;
}

/** React port of ui/tabs/tab_import.py. Column detection and the actual
 * insert/dedupe/industry-assignment logic live server-side (app/api's
 * import_.py, mirroring db/queries.py's import_leads) — this view only
 * collects files + options, previews them client-side for feedback, and
 * renders the ImportResult the backend hands back. */
export function ImportView({ onImported }: ImportViewProps) {
  const { toast } = useToast();
  const inputRef = React.useRef<HTMLInputElement>(null);

  const [dragActive, setDragActive] = React.useState(false);
  const [selected, setSelected] = React.useState<SelectedFile[]>([]);
  const [tooMany, setTooMany] = React.useState(false);

  const [tags, setTags] = React.useState<string[]>([]);
  const [industries, setIndustries] = React.useState<string[]>([]);
  const [industry, setIndustry] = React.useState("");
  const [industryNew, setIndustryNew] = React.useState("");

  const [submitting, setSubmitting] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ImportResult | null>(null);
  const [submittedIndustry, setSubmittedIndustry] = React.useState("");

  React.useEffect(() => {
    companiesApi
      .industries()
      .then(setIndustries)
      .catch(() => setIndustries([]));
  }, []);

  function addFiles(fileList: FileList | File[]) {
    const incoming = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith(".csv"));
    if (incoming.length === 0) return;

    setSelected((prev) => {
      const existingIds = new Set(prev.map((f) => f.id));
      const combined = [
        ...prev,
        ...incoming.map((file) => ({ id: crypto.randomUUID(), file, lineCount: null as number | null })),
      ];
      const capped = combined.slice(0, MAX_FILES);
      setTooMany(combined.length > MAX_FILES);

      capped
        .filter((f) => !existingIds.has(f.id))
        .forEach((f) => {
          f.file
            .text()
            .then((text) => {
              const rows = countRows(text);
              setSelected((cur) => cur.map((x) => (x.id === f.id ? { ...x, lineCount: rows } : x)));
            })
            .catch(() => {
              setSelected((cur) => cur.map((x) => (x.id === f.id ? { ...x, lineCount: 0 } : x)));
            });
        });

      return capped;
    });
  }

  function removeFile(id: string) {
    setSelected((prev) => {
      const next = prev.filter((f) => f.id !== id);
      if (next.length <= MAX_FILES) setTooMany(false);
      return next;
    });
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
  }

  function handleBrowse(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = "";
  }

  function handleIndustrySelect(value: string) {
    setIndustry(value);
    if (value !== ADD_NEW_INDUSTRY) setIndustryNew("");
  }

  async function handleSubmit() {
    if (selected.length === 0 || submitting) return;
    setFormError(null);

    let resolvedIndustry = "";
    if (industry === ADD_NEW_INDUSTRY) {
      const trimmed = industryNew.trim();
      if (!trimmed) {
        setFormError("Wpisz nazwę nowej branży lub wybierz istniejącą z listy.");
        return;
      }
      resolvedIndustry = trimmed;
    } else if (industry) {
      resolvedIndustry = industry;
    }

    setSubmitting(true);
    setResult(null);
    try {
      const res = await importApi.upload(
        selected.map((f) => f.file),
        tags,
        resolvedIndustry,
      );
      setSubmittedIndustry(resolvedIndustry);
      setResult(res);
      toast(
        res.added > 0
          ? { title: `Pomyślnie dodano ${res.added} lead(ów)`, variant: "success" }
          : { title: "Nie dodano żadnych nowych rekordów." },
      );
      onImported();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Import nie powiódł się — żadne dane nie zostały zapisane",
        description: errorMessage(err),
      });
    } finally {
      setSubmitting(false);
    }
  }

  const allPreviewed = selected.every((f) => f.lineCount !== null);
  const totalRows = selected.reduce((sum, f) => sum + (f.lineCount ?? 0), 0);

  return (
    <PageLayout>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold text-foreground">Importuj nowe kontakty</h1>
        <p className="text-sm text-muted-foreground">
          Wgraj pliki CSV (np. z Eventory, Livespace lub Clay), aby dodać rekordy do bazy.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-accent/30",
        )}
      >
        <UploadCloud className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-foreground">
          Przeciągnij i upuść pliki CSV tutaj, lub{" "}
          <span className="font-medium text-primary underline-offset-4 hover:underline">przeglądaj</span>
        </p>
        <p className="text-xs text-muted-foreground">Maksymalnie {MAX_FILES} plików na raz</p>
        <input ref={inputRef} type="file" multiple accept=".csv" className="hidden" onChange={handleBrowse} />
      </div>

      {tooMany && <p className="text-xs text-status-replied">Maksymalnie {MAX_FILES} plików na raz.</p>}

      {selected.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Wybrano {selected.length} plik(ów){allPreviewed ? ` — łącznie ~${totalRows} wierszy` : ""}.
          </p>
          <div className="space-y-2">
            {selected.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between gap-3 rounded-md border border-border bg-card/40 px-3 py-2"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{f.file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatSize(f.file.size)} · {f.lineCount === null ? "wczytywanie…" : `~${f.lineCount} wierszy`}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => removeFile(f.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      <Separator />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Przypisz tagi do importowanych leadów</Label>
          <MultiSelect
            options={[...AVAILABLE_TAGS]}
            value={tags}
            onChange={setTags}
            placeholder="Opcjonalne — wybierz tagi dla tej partii importu"
          />
        </div>
        <div className="space-y-1.5">
          <Label>Przypisz branżę firmom z tego importu</Label>
          <Select value={industry || undefined} onValueChange={handleIndustrySelect}>
            <SelectTrigger>
              <SelectValue placeholder="Opcjonalne — wybierz branżę dla firm z tej partii" />
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
          {industry === ADD_NEW_INDUSTRY && (
            <Input
              className="mt-2"
              placeholder="np. GreenTech / Energy"
              value={industryNew}
              onChange={(e) => setIndustryNew(e.target.value)}
            />
          )}
          <p className="text-xs text-muted-foreground">
            Branża zostanie ustawiona tylko firmom, które jeszcze jej nie mają — istniejące wartości nie są
            nadpisywane.
          </p>
        </div>
      </div>

      {formError && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
          <p className="text-sm text-destructive">{formError}</p>
        </div>
      )}

      <Button className="w-full" disabled={selected.length === 0 || submitting} onClick={handleSubmit}>
        {submitting ? "Importowanie…" : "Zapisz do bazy PostgreSQL"}
      </Button>

      {result && <ImportResultsPanel result={result} industry={submittedIndustry} />}
    </PageLayout>
  );
}

function ImportResultsPanel({ result, industry }: { result: ImportResult; industry: string }) {
  return (
    <div className="space-y-4 rounded-lg border border-border bg-card/40 p-4">
      <p className="text-sm font-semibold text-foreground">Wynik importu</p>

      <div className="space-y-2">
        {result.files.map((f, idx) => (
          <div key={`${f.filename}-${idx}`} className="rounded-md border border-border/70 p-3">
            <p className="text-sm font-medium text-foreground">
              {f.filename}
              {!f.error && <span className="text-muted-foreground"> — {f.rows} wierszy</span>}
            </p>

            {f.error ? (
              <p className="mt-1 flex items-start gap-1.5 text-sm text-destructive">
                <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {f.error}
              </p>
            ) : (
              <>
                {Object.keys(f.detected_columns).length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Wykryto kolumny:{" "}
                    {Object.entries(f.detected_columns)
                      .map(([field, col]) => `${field} → ${col}`)
                      .join(", ")}
                  </p>
                )}
                {f.missing_email_column && (
                  <p className="mt-1 flex items-start gap-1.5 text-sm text-status-replied">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    Brak kolumny email — leady trafią do bazy bez adresów (uwaga: bez emaila nie działa
                    deduplikacja).
                  </p>
                )}
              </>
            )}
          </div>
        ))}
      </div>

      <Separator />

      <div className="space-y-1.5">
        {result.added > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-status-opened">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Pomyślnie dodano {result.added} lead(ów)
          </p>
        )}
        {result.skipped_duplicates > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-status-replied">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Pominięto {result.skipped_duplicates} lead(ów) (duplikaty)
          </p>
        )}
        {result.skipped_invalid > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-status-replied">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Pominięto {result.skipped_invalid} całkowicie pusty(ch) wiersz(y)
          </p>
        )}
        {result.industry_set > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-status-opened">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Ustawiono branżę „{industry}” dla {result.industry_set} firm(y)
          </p>
        )}
        {result.industry_kept > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-status-new">
            <Info className="h-4 w-4 shrink-0" />
            {result.industry_kept} firm(y) miało już inną branżę — pozostawiono bez zmian
          </p>
        )}
        {result.added === 0 && (
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Info className="h-4 w-4 shrink-0" />
            Nie dodano żadnych nowych rekordów.
          </p>
        )}
      </div>
    </div>
  );
}
