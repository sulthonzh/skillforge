"use client";

import * as React from "react";
import { Plus, Braces, LayoutGrid, ChevronDown, Wand2, X, ArrowDown, Check, RefreshCw } from "lucide-react";
import { ToolRecommendationCard } from "./ToolRecommendationCard";
import { Button } from "./ui/button";
import { Input, Textarea } from "./ui/input";
import { Badge } from "./ui/badge";
import { Skeleton } from "./ui/skeleton";
import { useToast } from "./ui/toast";
import { api, ApiError } from "@/lib/api";
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
  function addSpecificTool(tool: Tool) {
    onChange({ ...manifest, tools: [...manifest.tools, tool] });
  }
  function replaceTool(index: number, tool: Tool) {
    const tools = manifest.tools.slice();
    tools[index] = tool;
    onChange({ ...manifest, tools });
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
              <div className="flex gap-1.5">
                <SuggestToolsButton manifest={manifest} onAdd={addSpecificTool} onReplace={replaceTool} />
                <Button size="xs" variant="outline" onClick={addTool}>
                  <Plus className="h-3 w-3" />
                  Add
                </Button>
              </div>
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

/**
 * SuggestToolsButton — opens a panel of AI-suggested tools for the current
 * manifest. Each suggestion can be added to the stack. Powered by
 * POST /api/chat/suggest-tools (catalog heuristics + optional LLM picks).
 */
function SuggestToolsButton({
  manifest,
  onAdd,
  onReplace,
}: {
  manifest: SkillManifest;
  onAdd: (tool: Tool) => void;
  onReplace: (index: number, tool: Tool) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [hint, setHint] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [suggestions, setSuggestions] = React.useState<Tool[]>([]);
  const { toast } = useToast();

  async function fetchSuggestions() {
    setLoading(true);
    try {
      const r = await api.suggestTools(manifest, hint);
      setSuggestions(r.suggestions);
      if (r.suggestions.length === 0) {
        toast({ variant: "info", title: "No new suggestions", description: "Try a more specific hint." });
      }
    } catch (e) {
      toast({ variant: "error", title: "Suggest failed", description: (e as ApiError).message });
    } finally {
      setLoading(false);
    }
  }

  function togglePanel() {
    const next = !open;
    setOpen(next);
    if (next && suggestions.length === 0 && !loading) fetchSuggestions();
  }

  return (
    <>
      <Button size="xs" variant="outline" onClick={togglePanel}>
        <Wand2 className="h-3 w-3" />
        Suggest
      </Button>
      {open && (
        <div className="mb-2 rounded-lg border border-primary/30 bg-accent/30 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="micro-label flex items-center gap-1.5">
              <Wand2 className="h-3 w-3" /> AI tool suggestions
            </span>
            <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mb-2 flex gap-2">
            <Input
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchSuggestions()}
              placeholder="e.g. swap the database for something with vector search"
              className="h-8 text-[12px]"
            />
            <Button size="xs" onClick={fetchSuggestions} loading={loading} disabled={loading}>
              {!loading && <RefreshCw className="h-3 w-3" />}
              Reload
            </Button>
          </div>
          {loading ? (
            <div className="space-y-1.5">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : suggestions.length === 0 ? (
            <p className="py-2 text-[12px] text-muted-foreground">No suggestions yet — refine the hint and reload.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {suggestions.map((s, i) => {
                const already = manifest.tools.some((t) => t.name.toLowerCase() === s.name.toLowerCase());
                return (
                  <li key={`${s.name}-${i}`} className="flex items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1.5">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate font-mono text-[12px] font-medium">{s.name}</span>
                        <Badge variant="mono">{s.category}</Badge>
                      </div>
                      {s.reason && <p className="truncate text-[11px] text-muted-foreground" title={s.reason}>{s.reason}</p>}
                    </div>
                    <Button
                      size="xs"
                      variant={already ? "ghost" : "outline"}
                      disabled={already}
                      onClick={() => {
                        onAdd(s);
                        setSuggestions((prev) => prev.filter((_, idx) => idx !== i));
                      }}
                    >
                      {already ? <Check className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                      {already ? "Added" : "Add"}
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </>
  );
}
