// Tiny fetch-based API client.
//
// In bundled mode the Web UI is served from the same origin as the API, so
// relative URLs ("/api/*", "/health") resolve for free. In dev mode the Next
// dev server runs on a different port (:3000) from the API (:8000), so set
// NEXT_PUBLIC_API_URL=http://localhost:8000 (or SKILLFORGE_WEB_API_URL, which
// the dev script maps) and requests will use that absolute base.

import type {
  BridgeToken,
  ChatPlanResponse,
  CompareResponse,
  ConnectionTest,
  DomainInfo,
  EvalRunDetail,
  EvalRunListItem,
  EvalRunSummary,
  EvalSuite,
  GenerateFilesResponse,
  InstallResponse,
  InstalledSkill,
  LocalPaths,
  MarketplaceListing,
  PendingApproval,
  ProviderConfigView,
  ProviderKind,
  ProviderPreset,
  ProviderUpdate,
  RegistryListResponse,
  SkillManifest,
  SuggestToolsResponse,
  Tool,
  ToolPreview,
  ToolRunResult,
  ValidateResponse,
} from "./types";

// Build-time constant. Empty string means same-origin (bundled mode).
const BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function url(path: string): string {
  return `${BASE}${path}`;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(url(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<T>(res);
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(url(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<T>(res);
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(url(path), { method: "GET" });
  return parseJson<T>(res);
}

async function delJson<T>(path: string): Promise<T> {
  const res = await fetch(url(path), { method: "DELETE" });
  return parseJson<T>(res);
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail ?? data;
    throw new ApiError(`Request to ${res.url} failed (${res.status})`, res.status, detail);
  }
  return data as T;
}

export const api = {
  health: () => getJson<{ status: string; version: string }>("/health"),

  planSkill: (message: string) =>
    postJson<ChatPlanResponse>("/api/chat/plan-skill", { message }),

  preview: (manifest: SkillManifest) =>
    postJson<GenerateFilesResponse>("/api/skills/preview", { manifest }),

  validate: (manifest: SkillManifest) =>
    postJson<ValidateResponse>("/api/skills/validate", { manifest }),

  install: (manifest: SkillManifest, overwrite = false) =>
    postJson<InstallResponse>("/api/skills/install", { manifest, overwrite }),

  listSkills: () => getJson<RegistryListResponse>("/api/registry/skills"),

  getSkillManifest: (name: string) =>
    getJson<SkillManifest>(`/api/registry/skills/${encodeURIComponent(name)}/manifest`),

  removeSkill: (name: string) =>
    delJson<{ removed: boolean; name: string }>(`/api/registry/skills/${encodeURIComponent(name)}`),

  domains: () => getJson<{ domains: DomainInfo[] }>("/api/templates/domains"),

  // ---- provider settings (S6) ----
  listProviders: () => getJson<{ providers: ProviderKind[] }>("/api/settings/providers"),
  listPresets: () => getJson<{ presets: ProviderPreset[] }>("/api/settings/presets"),
  getProvider: () => getJson<ProviderConfigView>("/api/settings/provider"),
  updateProvider: (update: ProviderUpdate) =>
    putJson<{ saved: boolean; provider: ProviderConfigView }>("/api/settings/provider", update),
  testProvider: (body: ProviderUpdate) =>
    postJson<ConnectionTest>("/api/settings/provider/test", body),
  listModels: () => getJson<{ provider: string; models: string[] }>("/api/settings/models"),

  // ---- tool suggestions (S7) ----
  suggestTools: (manifest: SkillManifest, hint: string, category?: string) =>
    postJson<SuggestToolsResponse>("/api/chat/suggest-tools", { manifest, hint, category }),

  // ---- local paths (so the UI shows the real configured dir) ----
  getPaths: () => getJson<LocalPaths>("/api/settings/paths"),

  // ---- eval harness ----
  listSuites: () => getJson<{ suites: EvalSuite[] }>("/api/eval/suites"),
  upsertSuite: (name: string, description: string, prompts: string[]) =>
    postJson<{ suite: EvalSuite }>("/api/eval/suites", { name, description, prompts }),
  deleteSuite: (name: string) =>
    delJson<{ removed: boolean; name: string }>(`/api/eval/suites/${encodeURIComponent(name)}`),

  runEval: (skill_name: string, suite_name?: string, extra_prompts?: string[], use_skill_examples = true) =>
    postJson<EvalRunSummary>("/api/eval/run", { skill_name, suite_name, extra_prompts, use_skill_examples }),

  listRuns: (skill?: string, suite?: string) =>
    getJson<{ runs: EvalRunListItem[] }>(
      `/api/eval/runs${skill ? `?skill=${encodeURIComponent(skill)}` : ""}${suite ? `${skill ? "&" : "?"}suite=${encodeURIComponent(suite)}` : ""}`,
    ),
  getRun: (id: number) => getJson<EvalRunDetail>(`/api/eval/runs/${id}`),
  deleteRun: (id: number) => delJson<{ removed: boolean }>(`/api/eval/runs/${id}`),
  overrideResult: (run_id: number, result_id: number, score: number, reasoning: string) =>
    postJson<{ id: number; score: number; reasoning: string; aggregate_score: number | null }>(
      `/api/eval/runs/${run_id}/results/${result_id}`,
      { score, reasoning },
    ),

  compare: (skills: string[], suite?: string) =>
    getJson<CompareResponse>(
      `/api/eval/compare?skills=${encodeURIComponent(skills.join(","))}${suite ? `&suite=${encodeURIComponent(suite)}` : ""}`,
    ),

  // ---- marketplace (local UI interface to the adapter) ----
  marketplaceSearch: (q = "", tags?: string[]) =>
    getJson<{ results: MarketplaceListing[]; count: number }>(
      `/api/marketplace/search?q=${encodeURIComponent(q)}${tags?.length ? `&tags=${encodeURIComponent(tags.join(","))}` : ""}`,
    ),
  marketplacePublish: (body: {
    skill_name: string;
    title?: string;
    description?: string;
    tags?: string[];
    license?: string;
    price_usd?: number;
    author?: string;
  }) => postJson<{ published: boolean; listing: MarketplaceListing }>("/api/marketplace/publish", body),
  marketplaceInstall: (listing_id: string) =>
    postJson<{ installed: boolean; pending_approval: string; listing: MarketplaceListing }>(
      "/api/marketplace/install",
      { listing_id },
    ),
  marketplacePending: () => getJson<{ pending: PendingApproval[] }>("/api/marketplace/pending"),
  marketplaceApprove: (id: string) =>
    postJson<{ installed: boolean; path?: string; new_version?: string }>(
      `/api/marketplace/pending/${id}/approve`,
      { overwrite: true },
    ),
  marketplaceReject: (id: string) =>
    postJson<{ rejected: boolean }>(`/api/marketplace/pending/${id}/reject`, {}),
  marketplacePairCode: () =>
    postJson<{ code: string; ttl_minutes: number }>("/api/marketplace/pair/code", {}),
  marketplaceTokens: () => getJson<{ tokens: BridgeToken[] }>("/api/marketplace/tokens"),
  marketplaceRevokeToken: (id: string) =>
    delJson<{ revoked: boolean }>(`/api/marketplace/tokens/${id}`),

  // ---- skill tools (generated helper scripts) ----
  listSkillTools: (skill_name: string) =>
    getJson<ToolPreview[]>(`/api/skills/${encodeURIComponent(skill_name)}/tools`),
  previewTool: (skill_name: string, script: string) =>
    postJson<ToolPreview>(`/api/skills/${encodeURIComponent(skill_name)}/tools/${encodeURIComponent(script)}/preview`, {}),
  runTool: (skill_name: string, script: string, confirm: boolean, args = "") =>
    postJson<ToolRunResult>(`/api/skills/${encodeURIComponent(skill_name)}/tools/${encodeURIComponent(script)}/run`, { confirm, args }),
};
