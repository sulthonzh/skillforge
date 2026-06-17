"use client";

import * as React from "react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import type { Tool } from "@/lib/types";

export function ToolRecommendationCard({
  tool,
  onChange,
  onRemove,
}: {
  tool: Tool;
  onChange: (next: Tool) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Input
              value={tool.name}
              onChange={(e) => onChange({ ...tool, name: e.target.value })}
              className="h-7 w-44 text-sm font-semibold"
            />
            <Input
              value={tool.category}
              onChange={(e) => onChange({ ...tool, category: e.target.value })}
              className="h-7 w-32 text-xs"
            />
          </div>
          <Input
            value={tool.reason}
            onChange={(e) => onChange({ ...tool, reason: e.target.value })}
            placeholder="Why this tool?"
            className="h-7 text-xs text-muted-foreground"
          />
        </div>
        <div className="flex flex-col items-end gap-2">
          <label className="flex cursor-pointer items-center gap-1 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={tool.enabled}
              onChange={(e) => onChange({ ...tool, enabled: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            {tool.enabled ? <Badge variant="success">on</Badge> : <Badge variant="outline">off</Badge>}
          </label>
          <Button variant="ghost" size="sm" onClick={onRemove} className="text-destructive">
            Remove
          </Button>
        </div>
      </div>
    </div>
  );
}
