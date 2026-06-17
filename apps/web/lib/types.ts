// Shared TypeScript types for the SkillForge Web UI.
// These mirror the Pydantic schemas in apps/api/skillforge_api/schemas.

export interface Tool {
  name: string;
  category: string;
  enabled: boolean;
  reason: string;
}

export interface SkillMeta {
  name: string;
  title: string;
  domain: string;
  description: string;
  version: string;
  status: string;
}

export interface SkillAI {
  generated_by: string;
  planner_model: string;
  created_at?: string | null;
}

export interface SkillManifest {
  schema_version: string;
  skill: SkillMeta;
  ai: SkillAI;
  tools: Tool[];
  architecture: { patterns: string[] };
  workflow: string[];
  best_practices: string[];
  output_standards: string[];
  outputs: {
    required_files: string[];
    required_directories: string[];
  };
  safety: {
    auto_execute_scripts: boolean;
    require_user_confirmation_before_install: boolean;
    allow_network_access: boolean;
  };
  example_prompts?: string[];
  example_outputs?: string[];
}

export interface ChatPlanResponse {
  manifest: SkillManifest;
  explanation: string;
}

export interface GeneratedFile {
  path: string;
  content: string;
}

export interface GenerateFilesResponse {
  files: GeneratedFile[];
}

export interface ValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
}

export interface ValidateResponse {
  valid: boolean;
  errors: ValidationIssue[];
}

export interface InstallResponse {
  installed: boolean;
  path: string;
  previous_version?: string | null;
  new_version?: string | null;
  version_bump_level?: string | null;
  version_bump_reason?: string | null;
}

export interface InstalledSkill {
  name: string;
  title: string;
  domain: string;
  path: string;
  version: string;
  installed_at?: string | null;
}

export interface RegistryListResponse {
  skills: InstalledSkill[];
}

export interface DomainInfo {
  key: string;
  label: string;
}

// ---- Settings / provider config ----

export type ProviderKind =
  | "mock"
  | "openai-compatible"
  | "ollama-local"
  | "anthropic"
  | "gemini"
  | "cohere";

export interface ProviderConfigView {
  provider: ProviderKind;
  openai_base_url: string;
  openai_api_key_set: boolean;
  openai_api_key_preview: string;
  ollama_base_url: string;
  anthropic_base_url: string;
  anthropic_api_key_set: boolean;
  anthropic_api_key_preview: string;
  gemini_base_url: string;
  gemini_api_key_set: boolean;
  gemini_api_key_preview: string;
  cohere_base_url: string;
  cohere_api_key_set: boolean;
  cohere_api_key_preview: string;
  model: string;
}

export interface ProviderUpdate {
  provider?: ProviderKind;
  openai_base_url?: string;
  openai_api_key?: string;
  ollama_base_url?: string;
  anthropic_base_url?: string;
  anthropic_api_key?: string;
  gemini_base_url?: string;
  gemini_api_key?: string;
  cohere_base_url?: string;
  cohere_api_key?: string;
  model?: string;
}

export interface ProviderPreset {
  key: string;
  label: string;
  base_url: string;
  default_model: string;
  docs_url: string;
}

export interface ConnectionTest {
  ok: boolean;
  detail: string;
}

export interface SuggestToolsResponse {
  suggestions: Tool[];
}

// ---- Local paths (so the UI never hardcodes ~/.skillforge) ----

export interface LocalPaths {
  skills_dir: string;
  config_path: string;
  db_path: string;
}

// ---- Eval harness ----

export interface EvalSuite {
  id?: number;
  name: string;
  description: string;
  prompts: string[];
  created_at?: string;
}

export interface EvalResult {
  id?: number;
  prompt: string;
  response: string;
  score: number | null;
  reasoning: string;
  status: "ok" | "error" | "skipped";
}

export interface EvalRunSummary {
  run_id: number;
  skill_name: string;
  suite_name: string;
  aggregate_score: number | null;
  results: EvalResult[];
}

export interface EvalRunListItem {
  id: number;
  skill_name: string;
  skill_version: string;
  suite_name: string;
  provider: string;
  model: string;
  aggregate_score: number | null;
  created_at: string;
}

export interface EvalRunDetail extends EvalRunListItem {
  results: EvalResult[];
}

export interface CompareRow {
  prompt: string;
  by_skill: Record<string, EvalResult>;
  winner: string | null;
  top_score: number;
}

export interface CompareResponse {
  skills: string[];
  matrix: CompareRow[];
  summary: Record<string, {
    aggregate_score: number | null;
    suite_name: string;
    run_id: number;
    created_at: string;
  }>;
}

// ---- Marketplace ----

export interface MarketplaceListing {
  id: string;
  name: string;
  title: string;
  description: string;
  version: string;
  author: string;
  tags: string[];
  license: string;
  price_usd: number;
  free: boolean;
  rating: number;
  reviews_count: number;
  downloads: number;
}

export interface BridgeToken {
  id: string;
  label: string;
  scopes: string[];
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
}

export interface PendingApproval {
  id: string;
  skill_name: string;
  source: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

