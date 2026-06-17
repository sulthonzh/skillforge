"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";

// Settings page reflects runtime backend status (provider/model/health) so users
// can confirm their config without dropping to a shell. Secrets are never
// exposed by the API.

interface BackendStatus {
  status: string;
  version: string;
}

export default function SettingsPage() {
  const [health, setHealth] = React.useState<BackendStatus | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Backend status and configuration. All secrets are read from environment variables on the
          server and never sent to the browser.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backend</CardTitle>
          <CardDescription>FastAPI service status.</CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">
              Backend unreachable: {error}. Start it with <code>skillforge serve</code> or{" "}
              <code>uvicorn skillforge_api.main:app</code>.
            </p>
          ) : health ? (
            <div className="flex items-center gap-3">
              <Badge variant="success">{health.status}</Badge>
              <span className="text-sm text-muted-foreground">version {health.version}</span>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Checking…</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI provider</CardTitle>
          <CardDescription>
            Configured via <code className="text-xs">SKILLFORGE_AI_PROVIDER</code> on the server.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              <Row k="Providers" v="mock · openai-compatible · ollama-local" />
              <Row k="OpenAI base URL" v="SKILLFORGE_OPENAI_BASE_URL" />
              <Row k="Ollama base URL" v="SKILLFORGE_OLLAMA_BASE_URL" />
              <Row k="Model" v="SKILLFORGE_MODEL" />
              <Row k="Skills dir" v="SKILLFORGE_SKILLS_DIR (default ~/.skillforge/skills)" />
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted-foreground">
            See <code>.env.example</code> in the repo root for the full list. The default{" "}
            <code>mock</code> provider works fully offline.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Safety</CardTitle>
          <CardDescription>SkillForge is safe by default.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Never auto-runs generated scripts.</li>
            <li>Never installs without an explicit click or <code>--yes</code>.</li>
            <li>Never overwrites an installed skill unless <code>overwrite</code> is set.</li>
            <li>Never sends local files to the AI unless you explicitly provide them.</li>
            <li>Secrets come only from environment variables.</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <tr>
      <td className="py-2 pr-4 font-medium">{k}</td>
      <td className="py-2 text-muted-foreground">{v}</td>
    </tr>
  );
}
