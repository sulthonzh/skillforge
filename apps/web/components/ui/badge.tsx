import * as React from "react";

type BadgeVariant = "default" | "secondary" | "outline" | "success" | "warning" | "mono";

const variants: Record<BadgeVariant, string> = {
  default: "bg-primary/12 text-primary border border-primary/20",
  secondary: "bg-secondary text-secondary-foreground border border-border",
  outline: "border border-border text-muted-foreground",
  success: "bg-success/12 text-success border border-success/25",
  warning: "bg-warning/12 text-warning border border-warning/25",
  // mono-chip: for tool categories, paths, code-like labels.
  mono: "bg-muted font-mono text-[11px] text-muted-foreground border border-border",
};

export function Badge({
  className = "",
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-none ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
