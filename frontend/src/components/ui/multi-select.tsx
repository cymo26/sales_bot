import * as React from "react";
import { ChevronDown, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface MultiSelectOption {
  value: string;
  label: string;
}

interface MultiSelectProps {
  options: (string | MultiSelectOption)[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  className?: string;
  searchable?: boolean;
}

/** Filter-bar multiselect: replaces Streamlit's st.multiselect. Renders
 * selected values as removable pills in the trigger and a checkbox list in
 * the popover, with an optional search box for long option lists. */
export function MultiSelect({ options, value, onChange, placeholder = "Wybierz...", className, searchable = true }: MultiSelectProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");

  const normalized: MultiSelectOption[] = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  const filtered = query ? normalized.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())) : normalized;

  function toggle(v: string) {
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  }

  function remove(v: string, e?: React.MouseEvent) {
    e?.stopPropagation();
    onChange(value.filter((x) => x !== v));
  }

  const labelOf = (v: string) => normalized.find((o) => o.value === v)?.label ?? v;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("h-9 w-full justify-between px-2 font-normal", value.length === 0 && "text-muted-foreground", className)}
        >
          <span className="flex flex-1 flex-wrap items-center gap-1 overflow-hidden py-0.5">
            {value.length === 0 && <span className="px-1 text-sm">{placeholder}</span>}
            {value.length > 0 && value.length <= 2 &&
              value.map((v) => (
                <Badge key={v} variant="secondary" className="gap-1 normal-case tracking-normal">
                  {labelOf(v)}
                  <X className="h-3 w-3 cursor-pointer opacity-70 hover:opacity-100" onClick={(e) => remove(v, e)} />
                </Badge>
              ))}
            {value.length > 2 && (
              <Badge variant="secondary" className="normal-case tracking-normal">
                {value.length} wybranych
              </Badge>
            )}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        {searchable && (
          <div className="p-2">
            <Input placeholder="Szukaj..." value={query} onChange={(e) => setQuery(e.target.value)} className="h-8" />
          </div>
        )}
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 && <div className="px-2 py-4 text-center text-sm text-muted-foreground">Brak wyników.</div>}
          {filtered.map((opt) => {
            const checked = value.includes(opt.value);
            return (
              <label
                key={opt.value}
                className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
              >
                <Checkbox checked={checked} onCheckedChange={() => toggle(opt.value)} />
                <span className="flex-1 truncate">{opt.label}</span>
              </label>
            );
          })}
        </div>
        {value.length > 0 && (
          <div className="border-t border-border p-1">
            <Button variant="ghost" size="sm" className="w-full justify-center text-xs" onClick={() => onChange([])}>
              Wyczyść wybór
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
