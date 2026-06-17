"use client";

import * as React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Cpu,
  KeyRound,
  Plug,
  Save,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type { ProviderConfigView, ProviderKind, ConnectionTest } from "@/lib/types";

const PROVIDERS: { value: ProviderKind; label: string; blurb: string }[] = [
  { value: "mock", label: "Mock", blurb: "Offline, deterministic. No key needed." },
  { value: "openai-compatible", label: "OpenAI-compatible", blurb: "OpenAI, OpenRouter, Together, Groq, vLLM…" },
  { value: "ollama-local", label: "Ollama (local)", blurb: "Local LLMs via Ollama. No API key." },
  { value: "anthropic", label: "Anthropic", blurb: "Claude models via the native Messages API." },
];

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Connect an AI provider. Configuration is stored locally and never sent anywhere else.
        </p>
      </div>
      <ProviderCard />
      <SafetyCard />
    </div>
  );
}

function ProviderCard() {
  const [cfg, setCfg] = React.useState<ProviderConfigView | null>(null);
  const [providers, setProviders] = React.useState<ProviderKind[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [provider, setProvider] = React.useState<ProviderKind>("mock");
  const [openaiBase, setOpenaiBase] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");
  const [ollamaBase, setOllamaBase] = React.useState("");
  const [anthropicBase, setAnthropicBase] = React.useState("");
  const [anthropicKey, setAnthropicKey] = React.useState("");
  const [model, setModel] = React.useState("");
  const [models, setModels] = React.useState<string[]>([]);
  const [testing, setTesting] = React.useState(false);
  const [testResult, setTestResult] = React.useState<ConnectionTest | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [loadingModels, setLoadingModels] = React.useState(false);
  const { toast } = useToast();

  // Load current config.
  React.useEffect(() => {
    Promise.all([api.getProvider(), api.listProviders()])
      .then(([c, p]) => {
        setCfg(c);
        setProviders(p.providers);
        setProvider(c.provider);
        setOpenaiBase(c.openai_base_url);
        setOllamaBase(c.ollama_base_url);
        setAnthropicBase(c.anthropic_base_url || "https://api.anthropic.com");
        setModel(c.model);
      })
      .catch((e: ApiError) => toast({ variant: "error", title: "Load failed", description: e.message }))
      .finally(() => setLoading(false));
  }, [toast]);

  // Refresh model list whenever provider changes (after first load).
  async function refreshModels(p: ProviderKind) {
    setLoadingModels(true);
    setModels([]);
    try {
      const r = await api.listModels();
      setModels(r.models);
    } catch {
      /* best-effort */
    } finally {
      setLoadingModels(false);
    }
  }

  async function save() {
    setSaving(true);
    setTestResult(null);
    try {
      const update: Record<string, string> = {
        provider,
        model,
        openai_base_url: openaiBase,
        ollama_base_url: ollamaBase,
        anthropic_base_url: anthropicBase,
      };
      if (apiKey) update.openai_api_key = apiKey;
      if (anthropicKey) update.anthropic_api_key = anthropicKey;
      const r = await api.updateProvider(update);
      setCfg(r.provider);
      setApiKey(""); // clear the field; key is now stored
      setAnthropicKey("");
      toast({ variant: "success", title: "Provider saved", description: `${r.provider.provider} · ${r.provider.model}` });
    } catch (e) {
      toast({ variant: "error", title: "Save failed", description: (e as ApiError).message });
    } finally {
      setSaving(false);
    }
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      const update: Record<string, string> = {
        provider,
        model,
        openai_base_url: openaiBase,
        ollama_base_url: ollamaBase,
        anthropic_base_url: anthropicBase,
      };
      if (apiKey) update.openai_api_key = apiKey;
      if (anthropicKey) update.anthropic_api_key = anthropicKey;
      const result = await api.testProvider(update);
      setTestResult(result);
      toast({
        variant: result.ok ? "success" : "error",
        title: result.ok ? "Connection OK" : "Connection failed",
        description: result.detail,
      });
    } catch (e) {
      toast({ variant: "error", title: "Test failed", description: (e as ApiError).message });
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="p-5">
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  const isMock = provider === "mock";
  const isOpenAI = provider === "openai-compatible";
  const isOllama = provider === "ollama-local";
  const isAnthropic = provider === "anthropic";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-muted-foreground" />
          AI provider
        </CardTitle>
        <CardDescription>
          Pick a provider and configure connection details. Active:{" "}
          <span className="font-mono text-foreground">{cfg?.provider}</span>
          {(cfg?.openai_api_key_set || cfg?.anthropic_api_key_set) && (
            <Badge variant="success" className="ml-2">key set</Badge>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {/* Provider selector */}
        <div>
          <span className="micro-label mb-2 block">Provider</span>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {PROVIDERS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => {
                  setProvider(p.value);
                  setTestResult(null);
                }}
                className={`rounded-lg border p-3 text-left transition-all ${
                  provider === p.value
                    ? "border-primary bg-accent"
                    : "border-border bg-card hover:border-border/80"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-medium">{p.label}</span>
                  {provider === p.value && <CheckCircle2 className="h-3.5 w-3.5 text-primary" />}
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{p.blurb}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Provider-specific fields */}
        {!isMock && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {isOpenAI && (
              <>
                <Field label="Base URL">
                  <Input value={openaiBase} onChange={(e) => setOpenaiBase(e.target.value)} className="font-mono text-[12px]" placeholder="https://api.openai.com/v1" />
                </Field>
                <Field label={`API key ${cfg?.openai_api_key_set ? "(stored — leave blank to keep)" : ""}`}>
                  <Input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={cfg?.openai_api_key_set ? "•••• stored ••••" : "sk-..."} className="font-mono text-[12px]" />
                </Field>
              </>
            )}
            {isOllama && (
              <Field label="Ollama base URL">
                <Input value={ollamaBase} onChange={(e) => setOllamaBase(e.target.value)} className="font-mono text-[12px]" placeholder="http://localhost:11434" />
              </Field>
            )}
            {isAnthropic && (
              <>
                <Field label="Base URL">
                  <Input value={anthropicBase} onChange={(e) => setAnthropicBase(e.target.value)} className="font-mono text-[12px]" placeholder="https://api.anthropic.com" />
                </Field>
                <Field label={`API key ${cfg?.anthropic_api_key_set ? "(stored — leave blank to keep)" : ""}`}>
                  <Input type="password" value={anthropicKey} onChange={(e) => setAnthropicKey(e.target.value)} placeholder={cfg?.anthropic_api_key_set ? "•••• stored ••••" : "sk-ant-..."} className="font-mono text-[12px]" />
                </Field>
              </>
            )}
            <Field label="Model">
              <div className="flex gap-2">
                <Input value={model} onChange={(e) => setModel(e.target.value)} className="font-mono text-[12px]" placeholder="model name" list="sf-models" />
                <Button variant="outline" size="sm" onClick={() => refreshModels(provider)} loading={loadingModels} disabled={isMock}>
                  <RefreshCw className="h-3 w-3" />
                </Button>
              </div>
              {models.length > 0 && (
                <datalist id="sf-models">
                  {models.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              )}
            </Field>
          </div>
        )}

        {/* Test result */}
        {testResult && (
          <div
            className={`flex items-center gap-2 rounded-md border p-3 text-[13px] ${
              testResult.ok
                ? "border-success/30 bg-success/5 text-success"
                : "border-destructive/30 bg-destructive/5 text-destructive"
            }`}
          >
            {testResult.ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
            <span className="flex-1">{testResult.detail}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={save} loading={saving}>
            {!saving && <Save className="h-3.5 w-3.5" />}
            Save
          </Button>
          <Button variant="outline" onClick={test} loading={testing} disabled={saving}>
            {!testing && <Plug className="h-3.5 w-3.5" />}
            Test connection
          </Button>
          {testing && <span className="text-[11px] text-muted-foreground">Probing endpoint…</span>}
        </div>
      </CardContent>
    </Card>
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

function SafetyCard() {
  const [configPath, setConfigPath] = React.useState("~/.skillforge/config.json");
  React.useEffect(() => {
    api.getPaths().then((p) => p.config_path && setConfigPath(p.config_path)).catch(() => {});
  }, []);
  return (
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
          <SafetyItem>The API key is written to <code className="font-mono">{configPath}</code> (chmod 600) and never logged.</SafetyItem>
          <SafetyItem>Provider settings are stored locally; nothing is sent anywhere except the provider you choose.</SafetyItem>
          <SafetyItem>Never auto-runs generated scripts.</SafetyItem>
          <SafetyItem>Never installs without an explicit action.</SafetyItem>
          <SafetyItem>Secrets come only from environment variables or the local config file.</SafetyItem>
        </ul>
      </CardContent>
    </Card>
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
