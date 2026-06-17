"use client";

import * as React from "react";
import type { GeneratedFile, SkillManifest } from "@/lib/types";
import { api, ApiError } from "@/lib/api";
import { Badge } from "./ui/badge";

// Fetches a preview whenever the manifest changes (debounced) and renders a
// tabbed view of SKILL.md / README.md / config.yaml plus every other file.

export function SkillPreview({ manifest }: { manifest: SkillManifest }) {
  const [files, setFiles] = React.useState<GeneratedFile[]>([]);
  const [active, setActive] = React.useState("SKILL.md");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Debounce so editing the manifest doesn't fire a request per keystroke.
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const handle = setTimeout(async () => {
      try {
        const result = await api.preview(manifest);
        if (!cancelled) {
          setFiles(result.files);
          // Keep the active tab if it still exists, else pick the first.
          if (!result.files.some((f) => f.path === active) && result.files[0]) {
            setActive(result.files[0].path);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setError((e as ApiError).message ?? "Preview failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest]);

  const current = files.find((f) => f.path === active);

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {files.map((f) => (
          <button
            key={f.path}
            onClick={() => setActive(f.path)}
            className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
              active === f.path
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-accent"
            }`}
          >
            {f.path}
          </button>
        ))}
        {loading && <Badge variant="secondary">rendering…</Badge>}
      </div>
      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      ) : (
        <pre className="scroll-thin flex-1 overflow-auto rounded-md border border-border bg-muted/30 p-3 text-xs leading-relaxed">
          <code>{current?.content ?? "No file selected."}</code>
        </pre>
      )}
    </div>
  );
}
