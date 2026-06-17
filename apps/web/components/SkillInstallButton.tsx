"use client";

import * as React from "react";
import { Download, CheckCircle2, AlertCircle, RotateCw } from "lucide-react";
import { Button } from "./ui/button";
import { api, ApiError } from "@/lib/api";
import { useToast } from "./ui/toast";
import type { SkillManifest } from "@/lib/types";

type State =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "installed"; path: string }
  | { kind: "conflict"; path: string };

export function SkillInstallButton({ manifest }: { manifest: SkillManifest }) {
  const [state, setState] = React.useState<State>({ kind: "idle" });
  const { toast } = useToast();

  async function install(overwrite = false) {
    setState({ kind: "working" });
    try {
      // Validate first for a friendly error before touching the filesystem.
      const v = await api.validate(manifest);
      if (!v.valid) {
        const errs = v.errors
          .filter((e) => e.severity === "error")
          .map((e) => `${e.code}: ${e.message}`);
        setState({ kind: "idle" });
        toast({
          variant: "error",
          title: "Manifest is invalid",
          description: errs.join("; ") || "Fix the errors and try again.",
        });
        return;
      }
      const res = await api.install(manifest, overwrite);
      setState({ kind: "installed", path: res.path });
      toast({
        variant: "success",
        title: `Installed ${manifest.skill.name}`,
        description: res.path,
      });
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 409) {
        setState({ kind: "conflict", path: manifest.skill.name });
        toast({
          variant: "info",
          title: "Already installed",
          description: "Click “Overwrite” to replace the existing skill.",
        });
      } else if (err.status === 400) {
        setState({ kind: "idle" });
        toast({
          variant: "error",
          title: "Validation failed",
          description:
            typeof err.detail === "string" ? err.detail : "The server rejected the manifest.",
        });
      } else {
        setState({ kind: "idle" });
        toast({ variant: "error", title: "Install failed", description: err.message });
      }
    }
  }

  if (state.kind === "installed") {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-[13px] text-success">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span className="font-medium">Installed</span>
          <code className="ml-1 truncate font-mono text-[11px] opacity-80" title={state.path}>
            {state.path}
          </code>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setState({ kind: "idle" })}>
          <RotateCw className="h-3 w-3" />
          Reinstall
        </Button>
      </div>
    );
  }

  const working = state.kind === "working";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={() => install(false)} loading={working}>
        {!working && <Download className="h-3.5 w-3.5" />}
        Install skill
      </Button>
      {state.kind === "conflict" && (
        <Button variant="outline" onClick={() => install(true)} disabled={working}>
          <AlertCircle className="h-3.5 w-3.5" />
          Overwrite &amp; install
        </Button>
      )}
      <p className="w-full text-[11px] text-muted-foreground">
        SkillForge never auto-runs generated scripts — install only writes files.
      </p>
    </div>
  );
}
