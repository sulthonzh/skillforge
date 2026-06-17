"use client";

import * as React from "react";
import {
  Play,
  GitCompare,
  FlaskConical,
  Trash2,
  CheckCircle2,
  XCircle,
  Trophy,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Plus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type {
  CompareResponse,
  EvalResult,
  EvalRunSummary,
  EvalSuite,
  InstalledSkill,
} from "@/lib/types";

export default function EvalPage() {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <FlaskConical className="h-5 w-5 text-primary" />
          Eval &amp; benchmark
        </h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Run skills against test prompts, auto-score with an LLM judge, and compare setups side-by-side.
        </p>
      </div>
      <Tabs defaultValue="run">
        <TabsList>
          <TabsTrigger value="run">
            <Play className="h-3 w-3" /> Run
          </TabsTrigger>
          <TabsTrigger value="compare">
            <GitCompare className="h-3 w-3" /> Compare
          </TabsTrigger>
        </TabsList>
        <TabsContent value="run" className="mt-4">
          <RunTab />
        </TabsContent>
        <TabsContent value="compare" className="mt-4">
          <CompareTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ============ Run tab ============

function RunTab() {
  const [skills, setSkills] = React.useState<InstalledSkill[]>([]);
  const [suites, setSuites] = React.useState<EvalSuite[]>([]);
  const [selectedSkill, setSelectedSkill] = React.useState("");
  const [selectedSuite, setSelectedSuite] = React.useState("");
  const [extraPrompt, setExtraPrompt] = React.useState("");
  const [running, setRunning] = React.useState(false);
  const [result, setResult] = React.useState<EvalRunSummary | null>(null);
  const { toast } = useToast();

  React.useEffect(() => {
    Promise.all([api.listSkills(), api.listSuites()])
      .then(([s, su]) => {
        setSkills(s.skills);
        setSuites(su.suites);
        if (s.skills[0]) setSelectedSkill(s.skills[0].name);
        if (su.suites[0]) setSelectedSuite(su.suites[0].name);
      })
      .catch((e: ApiError) => toast({ variant: "error", title: "Load failed", description: e.message }));
  }, [toast]);

  async function run() {
    if (!selectedSkill) return;
    setRunning(true);
    setResult(null);
    try {
      const extra = extraPrompt.trim() ? extraPrompt.split("\n").filter(Boolean) : [];
      const r = await api.runEval(
        selectedSkill,
        selectedSuite || undefined,
        extra,
        true,
      );
      setResult(r);
      toast({
        variant: "success",
        title: `Eval complete: ${r.skill_name}`,
        description: `Aggregate score ${r.aggregate_score ?? "n/a"}/10 across ${r.results.length} prompts`,
      });
    } catch (e) {
      toast({ variant: "error", title: "Eval failed", description: (e as ApiError).message });
    } finally {
      setRunning(false);
    }
  }

  if (skills.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <p className="text-[13px] text-muted-foreground">
            No installed skills to evaluate. Build and install one first.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Config */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="micro-label">Skill to evaluate</span>
              <select
                value={selectedSkill}
                onChange={(e) => setSelectedSkill(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
              >
                {skills.map((s) => (
                  <option key={s.name} value={s.name}>{s.name} (v{s.version})</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="micro-label">Test suite</span>
              <select
                value={selectedSuite}
                onChange={(e) => setSelectedSuite(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">— none —</option>
                {suites.map((s) => (
                  <option key={s.name} value={s.name}>{s.name} ({s.prompts.length})</option>
                ))}
              </select>
            </label>
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="micro-label">Extra prompts (one per line, optional)</span>
            <Textarea
              value={extraPrompt}
              onChange={(e) => setExtraPrompt(e.target.value)}
              rows={2}
              placeholder={"Add a custom test prompt…\nor a second one"}
            />
          </label>
          <div className="flex items-center gap-2">
            <Button onClick={run} loading={running} disabled={!selectedSkill}>
              {!running && <Play className="h-3.5 w-3.5" />}
              Run eval
            </Button>
            <span className="text-[11px] text-muted-foreground">
              Each skill also runs against its own example prompts.
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {running && (
        <Card>
          <CardContent className="space-y-2 p-4">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </CardContent>
        </Card>
      )}
      {result && <RunResults result={result} />}
    </div>
  );
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 8) return "text-success";
  if (score >= 5) return "text-warning";
  return "text-destructive";
}

function scoreBadgeVariant(score: number | null) {
  if (score === null) return "outline" as const;
  if (score >= 8) return "success" as const;
  if (score >= 5) return "warning" as const;
  return "outline" as const;
}

function RunResults({ result }: { result: EvalRunSummary }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-success" />
            Results — {result.skill_name}
          </CardTitle>
          {result.aggregate_score !== null && (
            <Badge variant={scoreBadgeVariant(result.aggregate_score)} className="text-sm">
              {result.aggregate_score}/10 avg
            </Badge>
          )}
        </div>
        <CardDescription>{result.results.length} prompts · run #{result.run_id}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {result.results.map((r, i) => (
          <ResultRow key={i} result={r} />
        ))}
      </CardContent>
    </Card>
  );
}

function ResultRow({ result }: { result: EvalResult }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="rounded-lg border border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 p-3 text-left"
      >
        {open ? <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium">{result.prompt}</p>
          {result.reasoning && <p className="truncate text-[11px] text-muted-foreground">{result.reasoning}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {result.status === "error" ? (
            <XCircle className="h-4 w-4 text-destructive" />
          ) : (
            <span className={`font-mono text-sm font-semibold ${scoreColor(result.score)}`}>
              {result.score?.toFixed(1) ?? "—"}
            </span>
          )}
        </div>
      </button>
      {open && result.response && (
        <pre className="scroll-thin max-h-60 overflow-auto whitespace-pre-wrap border-t border-border p-3 text-[12px] leading-relaxed text-muted-foreground">
          {result.response}
        </pre>
      )}
    </div>
  );
}

// ============ Compare tab ============

function CompareTab() {
  const [skills, setSkills] = React.useState<InstalledSkill[]>([]);
  const [suites, setSuites] = React.useState<EvalSuite[]>([]);
  const [picked, setPicked] = React.useState<Set<string>>(new Set());
  const [suite, setSuite] = React.useState("");
  const [comparing, setComparing] = React.useState(false);
  const [data, setData] = React.useState<CompareResponse | null>(null);
  const { toast } = useToast();

  React.useEffect(() => {
    Promise.all([api.listSkills(), api.listSuites()])
      .then(([s, su]) => {
        setSkills(s.skills);
        setSuites(su.suites);
        if (su.suites[0]) setSuite(su.suites[0].name);
      })
      .catch((e: ApiError) => toast({ variant: "error", title: "Load failed", description: e.message }));
  }, [toast]);

  function toggle(name: string) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  async function compare() {
    const names = Array.from(picked);
    if (names.length < 2) return;
    setComparing(true);
    setData(null);
    try {
      const r = await api.compare(names, suite || undefined);
      setData(r);
      if (r.skills.length < 2) {
        toast({
          variant: "info",
          title: "Need runs for both skills",
          description: "Run an eval for each selected skill first (in the Run tab).",
        });
      }
    } catch (e) {
      toast({ variant: "error", title: "Compare failed", description: (e as ApiError).message });
    } finally {
      setComparing(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:p-5">
          <div>
            <span className="micro-label mb-2 block">Skills to compare (pick 2+)</span>
            <div className="flex flex-wrap gap-1.5">
              {skills.map((s) => (
                <button
                  key={s.name}
                  type="button"
                  onClick={() => toggle(s.name)}
                  className={`rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors ${
                    picked.has(s.name)
                      ? "border-primary bg-accent text-accent-foreground"
                      : "border-border bg-card text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="micro-label">Suite</span>
              <select
                value={suite}
                onChange={(e) => setSuite(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">— any —</option>
                {suites.map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
            <Button onClick={compare} loading={comparing} disabled={picked.size < 2}>
              {!comparing && <GitCompare className="h-3.5 w-3.5" />}
              Compare ({picked.size})
            </Button>
          </div>
        </CardContent>
      </Card>

      {comparing && (
        <Card>
          <CardContent className="p-4">
            <Skeleton className="h-40 w-full" />
          </CardContent>
        </Card>
      )}

      {data && data.skills.length >= 2 && <CompareMatrix data={data} />}
    </div>
  );
}

function CompareMatrix({ data }: { data: CompareResponse }) {
  // Summary: each skill's aggregate + win count.
  const winCount: Record<string, number> = {};
  for (const row of data.matrix) {
    if (row.winner) winCount[row.winner] = (winCount[row.winner] ?? 0) + 1;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Trophy className="h-4 w-4 text-warning" /> Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data.skills.map((name) => {
              const agg = data.summary[name]?.aggregate_score;
              return (
                <div key={name} className="rounded-lg border border-border bg-card p-3">
                  <div className="flex items-center justify-between">
                    <span className="truncate font-mono text-[12px] font-medium">{name}</span>
                    {winCount[name] > 0 && <Badge variant="warning">{winCount[name]} wins</Badge>}
                  </div>
                  <p className={`mt-1 font-mono text-lg font-semibold ${scoreColor(agg)}`}>
                    {agg?.toFixed(2) ?? "—"}<span className="text-xs text-muted-foreground">/10</span>
                  </p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Per-prompt side-by-side */}
      <div className="flex flex-col gap-3">
        <span className="micro-label">Per-prompt comparison</span>
        {data.matrix.map((row, i) => (
          <CompareRow key={i} row={row} skills={data.skills} />
        ))}
      </div>
    </div>
  );
}

function CompareRow({
  row,
  skills,
}: {
  row: CompareResponse["matrix"][number];
  skills: string[];
}) {
  return (
    <Card>
      <CardContent className="p-3 sm:p-4">
        <p className="mb-3 text-[13px] font-medium">{row.prompt}</p>
        <div className={`grid gap-2 ${skills.length <= 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
          {skills.map((name) => {
            const res = row.by_skill[name];
            const isWinner = row.winner === name;
            if (!res) {
              return (
                <div key={name} className="rounded-lg border border-dashed border-border p-3 opacity-50">
                  <p className="font-mono text-[11px] text-muted-foreground">{name}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">no run</p>
                </div>
              );
            }
            return (
              <div
                key={name}
                className={`rounded-lg border p-3 ${isWinner ? "border-success/40 bg-success/5" : "border-border bg-card"}`}
              >
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="font-mono text-[11px] font-medium">{name}</span>
                  <div className="flex items-center gap-1">
                    {isWinner && <Trophy className="h-3 w-3 text-warning" />}
                    <span className={`font-mono text-sm font-semibold ${scoreColor(res.score)}`}>
                      {res.score?.toFixed(1) ?? "—"}
                    </span>
                  </div>
                </div>
                {res.response && (
                  <pre className="scroll-thin max-h-32 overflow-auto whitespace-pre-wrap text-[11px] leading-relaxed text-muted-foreground">
                    {res.response}
                  </pre>
                )}
                {res.reasoning && (
                  <p className="mt-1.5 border-t border-border/50 pt-1.5 text-[10px] italic text-muted-foreground">
                    {res.reasoning}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
