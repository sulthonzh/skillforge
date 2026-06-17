import * as React from "react";

// Shimmer placeholder. Uses the .sf-skeleton keyframe from globals.css.

export function Skeleton({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`sf-skeleton rounded-md ${className}`} {...props} />;
}
