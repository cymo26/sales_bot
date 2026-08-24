import { Button } from "@/components/ui/button";
import type { PageMeta } from "@/lib/types";

interface PaginationProps {
  meta: PageMeta;
  onPageChange: (page: number) => void;
  noun?: string;
}

/** Prev / "Strona X z Y" / Next — mirrors ui/components.py's render_pagination().
 * Renders nothing when there's only one page and nothing to show, same as
 * the original's early return. */
export function Pagination({ meta, onPageChange, noun = "rekordów" }: PaginationProps) {
  if (meta.pages <= 1 && meta.total <= 0) return null;

  return (
    <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
      <Button variant="outline" size="sm" disabled={meta.page <= 1} onClick={() => onPageChange(meta.page - 1)}>
        ← Poprzednia
      </Button>
      <div className="text-center text-xs font-semibold tracking-wide text-muted-foreground/70">
        Strona {meta.page} z {meta.pages} · {meta.total} {noun}
      </div>
      <Button variant="outline" size="sm" disabled={meta.page >= meta.pages} onClick={() => onPageChange(meta.page + 1)}>
        Następna →
      </Button>
    </div>
  );
}
