"use client";

import * as React from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { api, ApiError } from "@/lib/api";
import type { SkillManifest } from "@/lib/types";

// Validates, then installs on confirmation. Surfaces validation errors and the
// 409 "already installed" case with an explicit overwrite action.

export function SkillInstallButton({ manifest }: { manifest: SkillManifest }) {
  const [installing, setInstalling] = React.useState(false);
  const [result, setResult] = React.useState<{ ok: boolean; message: string; path?: string } | null>(
    null,
  );

  async function install(overwrite = false) {
    setInstalling(true);
    setResult(null);
    try {
      // Validate first for a friendly error before touching the filesystem.
      const v = await api.validate(manifest);
      if (!v.valid) {
        const errs = v.errors
          .filter((e) => e.severity === "error")
          .map((e) => `${e.code}: ${e.message}`);
        setResult({ ok: false, message: errs.join("; ") || "Manifest is invalid." });
        return;
      }
      const res = await api.install(manifest, overwrite);
      setResult({
        ok: true,
        message: `Installed ${manifest.skill.name}.`,
        path: res.path,
      });
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 409) {
        setResult({
          ok: false,
          message:
            "A skill with this name is already installed. Click overwrite to replace it.",
        });
      } else if (err.status === 400) {
        setResult({
          ok: false,
          message:
            typeof err.detail === "string" ? err.detail : "Validation failed on the server.",
        });
      } else {
        setResult({ ok: false, message: err.message });
      }
    } finally {
      setInstalling(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Button onClick={() => install(false)} disabled={installing}>
          {installing ? "Installing…" : "Install Skill"}
        </Button>
        {result && !result.ok && (
          <Button variant="outline" onClick={() => install(true)} disabled={installing}>
            Overwrite &amp; install
          </Button>
        )}
      </div>
      {result && (
        <div
          className={`rounded-md border p-3 text-sm ${
            result.ok
              ? "border-emerald-400/50 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
              : "border-destructive/40 bg-destructive/10 text-destructive"
          }`}
        >
          {result.ok ? "✓ " : "⚠ "}
          {result.message}
          {result.path && (
            <div className="mt-1 break-all font-mono text-xs opacity-80">{result.path}</div>
          )}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        <Badge variant="warning">safe</Badge> SkillForge never auto-runs generated scripts. Install
        writes files only.
      </p>
    </div>
  );
}
