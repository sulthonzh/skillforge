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

export type ProviderKind = "mock" | "openai-compatible" | "ollama-local";

export interface ProviderConfigView {
  provider: ProviderKind;
  openai_base_url: string;
  openai_api_key_set: boolean;
  openai_api_key_preview: string;
  ollama_base_url: string;
  model: string;
}

export interface ProviderUpdate {
  provider?: ProviderKind;
  openai_base_url?: string;
  openai_api_key?: string;
  ollama_base_url?: string;
  model?: string;
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

