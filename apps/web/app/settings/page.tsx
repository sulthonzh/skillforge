"use client";

import * as React from "react";
import { CheckCircle2, AlertTriangle, ShieldCheck, Cpu, KeyRound } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";

export default function SettingsPage() {
  const [health, setHealth] = React.useState<{ status: string; version: string } | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h))
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Backend status and configuration. Secrets are read from environment variables on the
          server and never sent to the browser.
        </p>
      </div>

      {/* Backend status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-muted-foreground" />
            Backend
          </CardTitle>
          <CardDescription>FastAPI service status</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-5 w-32" />
          ) : error ? (
            <div className="flex items-center gap-2 text-[13px] text-destructive">
              <AlertTriangle className="h-4 w-4" />
              Backend unreachable. Start it with{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">skillforge serve</code>.
            </div>
          ) : health ? (
            <div className="flex items-center gap-2">
              <Badge variant="success">
                <CheckCircle2 className="h-3 w-3" /> {health.status}
              </Badge>
              <span className="text-[12px] text-muted-foreground">v{health.version}</span>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* AI provider config */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-muted-foreground" />
            AI provider
          </CardTitle>
          <CardDescription>Configured via environment variables on the server</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="divide-y divide-border overflow-hidden rounded-md border border-border">
            <Row label="Providers" value="mock · openai-compatible · ollama-local" />
            <Row label="OpenAI base URL" value="SKILLFORGE_OPENAI_BASE_URL" mono />
            <Row label="Ollama base URL" value="SKILLFORGE_OLLAMA_BASE_URL" mono />
            <Row label="Model" value="SKILLFORGE_MODEL" mono />
            <Row label="Skills dir" value="SKILLFORGE_SKILLS_DIR" mono />
            <Row label="Web UI dir" value="SKILLFORGE_WEB_DIR" mono />
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground">
            See <code className="font-mono">.env.example</code> in the repo root. The default{" "}
            <code className="font-mono">mock</code> provider works fully offline.
          </p>
        </CardContent>
      </Card>

      {/* Safety */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-muted-foreground" />
            Safety
          </CardTitle>
          <CardDescription>SkillForge is safe by default</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5 text-[13px] text-muted-foreground">
            <SafetyItem>Never auto-runs generated scripts.</SafetyItem>
            <SafetyItem>Never installs without an explicit action.</SafetyItem>
            <SafetyItem>Never overwrites a skill unless <code className="font-mono">overwrite</code> is set.</SafetyItem>
            <SafetyItem>Never sends local files to the AI unless you provide them.</SafetyItem>
            <SafetyItem>Secrets come only from environment variables.</SafetyItem>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2">
      <span className="text-[12px] font-medium">{label}</span>
      <span className={`truncate text-[12px] text-muted-foreground ${mono ? "font-mono" : ""}`}>
        {value}
      </span>
    </div>
  );
}

function SafetyItem({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
      <span>{children}</span>
    </li>
  );
}
