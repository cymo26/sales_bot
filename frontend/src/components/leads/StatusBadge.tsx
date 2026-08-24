import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS, type LeadStatus } from "@/lib/types";

const VARIANT_BY_STATUS: Record<string, "new" | "sent" | "opened" | "replied" | "bounced"> = {
  new: "new",
  sent: "sent",
  opened: "opened",
  replied: "replied",
  bounced: "bounced",
};

/** Mirrors ui/styles.py's .lb-* badge classes and ui/constants.py's Polish
 * status labels 1:1. Unknown statuses fall back to the "new" look with the
 * raw value as the label, matching db/queries.py's status_label() passthrough. */
export function StatusBadge({ status }: { status: string }) {
  const variant = VARIANT_BY_STATUS[status] ?? "new";
  const label = STATUS_LABELS[status as LeadStatus] ?? status;
  return <Badge variant={variant}>{label}</Badge>;
}
