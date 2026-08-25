import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[0.68rem] font-bold uppercase tracking-wide transition-colors whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/15 text-primary",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-foreground/70",
        // Lead status badges — colors match ui/styles.py's .lb-* classes 1:1.
        new: "border-status-new/30 bg-status-new/10 text-status-new",
        sent: "border-status-sent/30 bg-status-sent/10 text-status-sent",
        opened: "border-status-opened/30 bg-status-opened/10 text-status-opened",
        replied: "border-status-replied/30 bg-status-replied/10 text-status-replied",
        bounced: "border-status-bounced/30 bg-status-bounced/10 text-status-bounced",
        // Event-tag pills — colors match ui/styles.py's .tag-* classes 1:1.
        jdd: "border-tag-jdd/30 bg-tag-jdd/10 text-tag-jdd",
        omh: "border-tag-omh/30 bg-tag-omh/10 text-tag-omh",
        confidence: "border-tag-confidence/30 bg-tag-confidence/10 text-tag-confidence",
        tagDefault: "border-tag-default/30 bg-tag-default/10 text-tag-default",
        // Livespace ownership warnings — distinct from status/tag badges on
        // purpose: these are cross-system warnings, not our own data.
        livespaceOwned: "border-destructive/40 bg-destructive/10 text-destructive",
        livespaceEngaged: "border-status-replied/40 bg-status-replied/10 text-status-replied",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
