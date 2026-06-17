"use client";

import * as React from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/input";
import { api, ApiError } from "@/lib/api";
import type { ChatPlanResponse } from "@/lib/types";

const EXAMPLES = [
  "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest.",
  "Data engineering skill for Airflow, dbt, BigQuery, data quality checks, and CI/CD.",
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

  async function submit(msg?: string) {
    const text = (msg ?? message).trim();
    if (!text) return;
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
          : `AI planning failed (${err.status}). Is the backend running on :8000?`,
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Describe your engineering need in plain language…"
        rows={4}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
        }}
      />
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Press <kbd className="rounded bg-muted px-1">⌘/Ctrl + Enter</kbd> to plan.
        </p>
        <Button onClick={() => submit()} disabled={loading || !message.trim()}>
          {loading ? "Planning…" : "Plan Skill"}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setMessage(ex);
              submit(ex);
            }}
            disabled={loading}
            className="rounded-full border border-border bg-background px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
          >
            {ex.length > 60 ? ex.slice(0, 57) + "…" : ex}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
    </div>
  );
}
