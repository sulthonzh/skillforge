"use client";

import * as React from "react";
import { ArrowRight, Sparkles, TriangleAlert } from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/input";
import { api, ApiError } from "@/lib/api";
import type { ChatPlanResponse } from "@/lib/types";

const EXAMPLES = [
  "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest.",
  "Data engineering skill for Airflow, dbt, BigQuery, data quality checks.",
  "I need an AI RAG skill with LangChain and pgvector.",
  "DevOps skill for Kubernetes, Helm, and Terraform.",
];

export function ChatPanel({
  onPlanned,
}: {
  onPlanned: (result: ChatPlanResponse, message: string) => void;
}) {
  const [message, setMessage] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // Tier 0.2: detect silent mock fallback so we can warn the user that their
  // configured AI provider isn't actually being used.
  const [degraded, setDegraded] = React.useState(false);
  const [fallbackReason, setFallbackReason] = React.useState<string | null>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    let cancelled = false;
    api
      .getProvider()
      .then((cfg) => {
        if (cancelled) return;
        if (cfg.degraded) {
          setDegraded(true);
          setFallbackReason(cfg.fallback_reason ?? null);
        }
      })
      .catch(() => {
        /* non-fatal — the banner is best-effort */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(msg?: string) {
    const text = (msg ?? message).trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.planSkill(text);
      onPlanned(result, text);
    } catch (e) {
      const err = e as ApiError;
      setError(
        typeof err.detail === "string"
          ? err.detail
          : `AI planning failed (${err.status}). Is the backend running?`,
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {degraded && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-[12px] text-amber-700 dark:text-amber-400">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <div className="flex-1">
            <span className="font-medium">Running in mock mode.</span> Your
            configured AI provider isn&apos;t ready
            {fallbackReason ? ` (${fallbackReason})` : ""}, so skills are
            generated from heuristics, not AI.{" "}
            <a href="/settings" className="underline underline-offset-2">
              Set your API key in Settings
            </a>
            .
          </div>
        </div>
      )}

      <div className="relative">
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Describe your engineering need in plain language…  e.g. a backend service with Postgres, migrations, and tests"
          rows={4}
          className="resize-none pr-4 text-[14px]"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
          }}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="hidden text-[11px] text-muted-foreground sm:block">
          Press{" "}
          <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
            ⌘ Enter
          </kbd>{" "}
          to plan
        </p>
        <Button
          onClick={() => submit()}
          loading={loading}
          disabled={!message.trim()}
          className="ml-auto"
        >
          {!loading && <Sparkles className="h-3.5 w-3.5" />}
          {loading ? "Planning…" : "Plan skill"}
          {!loading && <ArrowRight className="h-3.5 w-3.5" />}
        </Button>
      </div>

      {/* Example chips */}
      <div className="flex flex-wrap gap-1.5 pt-1">
        <span className="micro-label mr-1 self-center">Try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setMessage(ex);
              submit(ex);
            }}
            disabled={loading}
            className="max-w-full truncate rounded-full border border-border bg-card px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/30 hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
            title={ex}
          >
            {ex.length > 52 ? ex.slice(0, 50) + "…" : ex}
          </button>
        ))}
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-[13px] text-destructive">
          <span className="font-medium">Couldn&apos;t plan:</span>
          <span className="flex-1">{error}</span>
        </div>
      )}
    </div>
  );
}
