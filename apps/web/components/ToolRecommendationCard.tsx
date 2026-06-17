"use client";

import * as React from "react";
import { Pencil, Trash2, ChevronDown, GripVertical } from "lucide-react";
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
  const [editing, setEditing] = React.useState(false);

  return (
    <div
      className={`group rounded-lg border bg-card transition-colors ${
        tool.enabled ? "border-border hover:border-border/80" : "border-border/50 opacity-60"
      }`}
    >
      {/* Row view — always visible */}
      <div className="flex items-center gap-2.5 px-3 py-2">
        <GripVertical className="h-4 w-4 shrink-0 cursor-grab text-muted-foreground/30 active:cursor-grabbing" />

        {/* Enable toggle (custom switch) */}
        <button
          type="button"
          role="switch"
          aria-checked={tool.enabled}
          onClick={() => onChange({ ...tool, enabled: !tool.enabled })}
          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            tool.enabled ? "bg-primary" : "bg-muted-foreground/30"
          }`}
          title={tool.enabled ? "Enabled" : "Disabled"}
        >
          <span
            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
              tool.enabled ? "translate-x-4.5" : "translate-x-1"
            }`}
            style={{ transform: `translateX(${tool.enabled ? "18px" : "3px"})` }}
          />
        </button>

        <span className="min-w-0 flex-1 truncate font-mono text-[13px] font-medium">
          {tool.name}
        </span>

        <Badge variant="mono">{tool.category}</Badge>

        {/* Hover actions */}
        <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setEditing((v) => !v)}
            title={editing ? "Collapse" : "Edit"}
          >
            {editing ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <Pencil className="h-3.5 w-3.5" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={onRemove}
            title="Remove"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Reason line (truncated) — always shown when not editing */}
      {!editing && tool.reason && (
        <div className="border-t border-border/50 px-3 py-1.5 pl-[60px]">
          <p className="truncate text-[12px] leading-relaxed text-muted-foreground" title={tool.reason}>
            {tool.reason}
          </p>
        </div>
      )}

      {/* Edit form — expandable */}
      {editing && (
        <div className="space-y-2.5 border-t border-border/50 p-3">
          <div className="grid grid-cols-2 gap-2">
            <LabeledInput
              label="Name"
              value={tool.name}
              onChange={(v) => onChange({ ...tool, name: v })}
              mono
            />
            <LabeledInput
              label="Category"
              value={tool.category}
              onChange={(v) => onChange({ ...tool, category: v })}
              mono
            />
          </div>
          <LabeledInput
            label="Reason"
            value={tool.reason}
            onChange={(v) => onChange({ ...tool, reason: v })}
            textarea
          />
        </div>
      )}
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
  textarea = false,
  mono = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  textarea?: boolean;
  mono?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="micro-label">{label}</span>
      {textarea ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className="flex w-full rounded-md border border-input bg-background px-3 py-1.5 text-[13px] leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      ) : (
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`h-8 text-[13px] ${mono ? "font-mono" : ""}`}
        />
      )}
    </label>
  );
}
