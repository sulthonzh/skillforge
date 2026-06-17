// Tiny fetch-based API client.
//
// In bundled mode the Web UI is served from the same origin as the API, so
// relative URLs ("/api/*", "/health") resolve for free. In dev mode the Next
// dev server runs on a different port (:3000) from the API (:8000), so set
// NEXT_PUBLIC_API_URL=http://localhost:8000 (or SKILLFORGE_WEB_API_URL, which
// the dev script maps) and requests will use that absolute base.

import type {
  ChatPlanResponse,
  ConnectionTest,
  DomainInfo,
  GenerateFilesResponse,
  InstallResponse,
  LocalPaths,
  ProviderConfigView,
  ProviderKind,
  ProviderUpdate,
  RegistryListResponse,
  SkillManifest,
  SuggestToolsResponse,
  Tool,
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
};
