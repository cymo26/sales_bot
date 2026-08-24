import { Badge } from "@/components/ui/badge";
import { AVAILABLE_TAGS } from "@/lib/types";

const VARIANT_BY_TAG: Record<string, "jdd" | "omh" | "confidence"> = {
  JDD: "jdd",
  OMH: "omh",
  CONFIDENCE: "confidence",
};

/** Renders a lead's event tags as pills — mirrors ui/components.py's
 * render_tags(): known tags (AVAILABLE_TAGS) get their dedicated color,
 * anything else falls back to the neutral "tagDefault" look. */
export function TagPills({ tags }: { tags: string[] }) {
  if (tags.length === 0) return <span className="text-sm text-muted-foreground/40">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} variant={VARIANT_BY_TAG[tag.toUpperCase()] ?? "tagDefault"}>
          {tag}
        </Badge>
      ))}
    </div>
  );
}

export { AVAILABLE_TAGS };
