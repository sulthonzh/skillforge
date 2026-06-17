"use client";

import * as React from "react";
import { ToolRecommendationCard } from "./ToolRecommendationCard";
import { Button } from "./ui/button";
import { Input, Textarea } from "./ui/input";
import { Badge } from "./ui/badge";
import type { SkillManifest, Tool } from "@/lib/types";

// Editable summary of a manifest. Tool cards are the primary surface; the raw
// JSON view is for power users who want to edit fields the cards don't expose.

export function SkillManifestEditor({
  manifest,
  onChange,
}: {
  manifest: SkillManifest;
  onChange: (next: SkillManifest) => void;
}) {
  const [view, setView] = React.useState<"cards" | "json">("cards");
  const [jsonText, setJsonText] = React.useState("");
  const [jsonError, setJsonError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (view === "json") setJsonText(JSON.stringify(manifest, null, 2));
  }, [view, manifest]);

  function updateTool(index: number, next: Tool) {
    const tools = manifest.tools.slice();
    tools[index] = next;
    onChange({ ...manifest, tools });
  }
  function removeTool(index: number) {
    const tools = manifest.tools.slice();
    tools.splice(index, 1);
    onChange({ ...manifest, tools });
  }
  function addTool() {
    onChange({
      ...manifest,
      tools: [
        ...manifest.tools,
        { name: "New Tool", category: "misc", enabled: true, reason: "" },
      ],
    });
  }

  function applyJson() {
    try {
      const parsed = JSON.parse(jsonText) as SkillManifest;
      setJsonError(null);
      onChange(parsed);
    } catch (e) {
      setJsonError((e as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Skill name</span>
          <Input
            value={manifest.skill.name}
            onChange={(e) =>
              onChange({ ...manifest, skill: { ...manifest.skill, name: e.target.value } })
            }
            className="h-8 w-56 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Domain</span>
          <Input
            value={manifest.skill.domain}
            onChange={(e) =>
              onChange({ ...manifest, skill: { ...manifest.skill, domain: e.target.value } })
            }
            className="h-8 w-44 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Version</span>
          <Input
            value={manifest.skill.version}
            onChange={(e) =>
              onChange({ ...manifest, skill: { ...manifest.skill, version: e.target.value } })
            }
            className="h-8 w-24 text-sm"
          />
        </label>
        <div className="ml-auto flex gap-1 rounded-md border border-border p-0.5">
          <Button
            size="sm"
            variant={view === "cards" ? "default" : "ghost"}
            onClick={() => setView("cards")}
          >
            Cards
          </Button>
          <Button
            size="sm"
            variant={view === "json" ? "default" : "ghost"}
            onClick={() => setView("json")}
          >
            JSON
          </Button>
        </div>
      </div>

      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted-foreground">Description</span>
        <Textarea
          value={manifest.skill.description}
          onChange={(e) =>
            onChange({ ...manifest, skill: { ...manifest.skill, description: e.target.value } })
          }
          rows={2}
        />
      </label>

      {view === "cards" ? (
        <>
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold">
              Tools <Badge variant="secondary">{manifest.tools.length}</Badge>
            </h4>
            <Button size="sm" variant="outline" onClick={addTool}>
              + Add tool
            </Button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {manifest.tools.map((t, i) => (
              <ToolRecommendationCard
                key={`${t.name}-${i}`}
                tool={t}
                onChange={(next) => updateTool(i, next)}
                onRemove={() => removeTool(i)}
              />
            ))}
          </div>

          <details className="rounded-md border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Workflow, best practices &amp; standards
            </summary>
            <div className="mt-3 grid gap-3">
              <ListEditor
                label="Workflow steps"
                items={manifest.workflow}
                onChange={(workflow) => onChange({ ...manifest, workflow })}
              />
              <ListEditor
                label="Best practices"
                items={manifest.best_practices}
                onChange={(best_practices) => onChange({ ...manifest, best_practices })}
              />
              <ListEditor
                label="Output standards"
                items={manifest.output_standards}
                onChange={(output_standards) => onChange({ ...manifest, output_standards })}
              />
              <ListEditor
                label="Architecture patterns"
                items={manifest.architecture.patterns}
                onChange={(patterns) =>
                  onChange({ ...manifest, architecture: { patterns } })
                }
              />
            </div>
          </details>
        </>
      ) : (
        <div className="flex flex-col gap-2">
          <Textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            rows={20}
            className="scroll-thin font-mono text-xs"
            spellCheck={false}
          />
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={applyJson}>
              Apply JSON
            </Button>
            {jsonError && <span className="text-xs text-destructive">{jsonError}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function ListEditor({
  label,
  items,
  onChange,
}: {
  label: string;
  items: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <Textarea
        value={items.join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n").filter(Boolean))}
        rows={Math.min(8, Math.max(2, items.length))}
        className="text-xs"
      />
    </label>
  );
}
