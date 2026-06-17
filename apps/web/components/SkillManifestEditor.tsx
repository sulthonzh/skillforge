"use client";

import * as React from "react";
import { Plus, Braces, LayoutGrid, ChevronDown } from "lucide-react";
import { ToolRecommendationCard } from "./ToolRecommendationCard";
import { Button } from "./ui/button";
import { Input, Textarea } from "./ui/input";
import { Badge } from "./ui/badge";
import type { SkillManifest, Tool } from "@/lib/types";

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

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
        { name: "new-tool", category: "misc", enabled: true, reason: "" },
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

  const enabledCount = manifest.tools.filter((t) => t.enabled).length;

  return (
    <div className="flex flex-col gap-5">
      {/* View switch */}
      <div className="flex items-center justify-between">
        <div className="inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted/40 p-0.5">
          <Button
            size="xs"
            variant={view === "cards" ? "default" : "ghost"}
            onClick={() => setView("cards")}
            className={view === "cards" ? "" : "text-muted-foreground"}
          >
            <LayoutGrid className="h-3 w-3" />
            Editor
          </Button>
          <Button
            size="xs"
            variant={view === "json" ? "default" : "ghost"}
            onClick={() => setView("json")}
            className={view === "json" ? "" : "text-muted-foreground"}
          >
            <Braces className="h-3 w-3" />
            JSON
          </Button>
        </div>
      </div>

      {/* Skill meta — always shown */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Skill name">
          <Input
            value={manifest.skill.name}
            onChange={(e) =>
              onChange({ ...manifest, skill: { ...manifest.skill, name: e.target.value } })
            }
            className="font-mono"
          />
        </Field>
        <Field label="Domain">
          <Input
            value={manifest.skill.domain}
            onChange={(e) =>
              onChange({ ...manifest, skill: { ...manifest.skill, domain: e.target.value } })
            }
          />
        </Field>
        <Field label="Version">
          <Input
            value={manifest.skill.version}
            onChange={(e) =>
              onChange({ ...manifest, skill: { ...manifest.skill, version: e.target.value } })
            }
            className="font-mono"
          />
        </Field>
      </div>
      <Field label="Description">
        <Textarea
          value={manifest.skill.description}
          onChange={(e) =>
            onChange({ ...manifest, skill: { ...manifest.skill, description: e.target.value } })
          }
          rows={2}
        />
      </Field>

      {view === "cards" ? (
        <>
          {/* Tools */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="micro-label">Tools</span>
                <Badge variant="secondary">
                  {enabledCount}/{manifest.tools.length}
                </Badge>
              </div>
              <Button size="xs" variant="outline" onClick={addTool}>
                <Plus className="h-3 w-3" />
                Add
              </Button>
            </div>
            <div className="flex flex-col gap-1.5">
              {manifest.tools.map((t, i) => (
                <ToolRecommendationCard
                  key={`${t.name}-${i}`}
                  tool={t}
                  onChange={(next) => updateTool(i, next)}
                  onRemove={() => removeTool(i)}
                />
              ))}
            </div>
          </div>

          {/* Collapsible detail sections */}
          <CollapsibleSection
            title="Workflow"
            count={manifest.workflow.length}
            items={manifest.workflow}
            onChange={(workflow) => onChange({ ...manifest, workflow })}
          />
          <CollapsibleSection
            title="Best practices"
            count={manifest.best_practices.length}
            items={manifest.best_practices}
            onChange={(best_practices) => onChange({ ...manifest, best_practices })}
          />
          <CollapsibleSection
            title="Output standards"
            count={manifest.output_standards.length}
            items={manifest.output_standards}
            onChange={(output_standards) => onChange({ ...manifest, output_standards })}
          />
          <CollapsibleSection
            title="Architecture patterns"
            count={manifest.architecture.patterns.length}
            items={manifest.architecture.patterns}
            onChange={(patterns) =>
              onChange({ ...manifest, architecture: { patterns } })
            }
          />
        </>
      ) : (
        <div className="flex flex-col gap-2">
          <Textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            rows={22}
            spellCheck={false}
            className="scroll-thin font-mono text-[12px] leading-relaxed"
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="micro-label">{label}</span>
      {children}
    </label>
  );
}

function CollapsibleSection({
  title,
  count,
  items,
  onChange,
}: {
  title: string;
  count: number;
  items: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="micro-label">{title}</span>
          <Badge variant="outline">{count}</Badge>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="border-t border-border p-3">
          <textarea
            value={items.join("\n")}
            onChange={(e) => onChange(e.target.value.split("\n"))}
            rows={Math.min(10, Math.max(3, items.length + 1))}
            className="scroll-thin w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-[13px] leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder={`One ${title.toLowerCase().replace(/s$/, "")} per line…`}
          />
        </div>
      )}
    </div>
  );
}
