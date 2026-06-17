"use client";

import * as React from "react";
import { FileCode2, RefreshCw } from "lucide-react";
import type { GeneratedFile, SkillManifest } from "@/lib/types";
import { api, ApiError } from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Skeleton } from "./ui/skeleton";

export function SkillPreview({ manifest }: { manifest: SkillManifest }) {
  const [files, setFiles] = React.useState<GeneratedFile[]>([]);
  const [active, setActive] = React.useState("SKILL.md");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const lastSignature = React.useRef("");

  React.useEffect(() => {
    let cancelled = false;
    // Debounce — and skip refiring if the manifest only changed by whitespace.
    const signature = JSON.stringify(manifest);
    if (signature === lastSignature.current) return;
    lastSignature.current = signature;

    setLoading(true);
    setError(null);
    const handle = setTimeout(async () => {
      try {
        const result = await api.preview(manifest);
        if (!cancelled) {
          setFiles(result.files);
          if (!result.files.some((f) => f.path === active) && result.files[0]) {
            setActive(result.files[0].path);
          }
        }
      } catch (e) {
        if (!cancelled) setError((e as ApiError).message ?? "Preview failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest]);

  const current = files.find((f) => f.path === active);
  const isEmpty = files.length === 0;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Tabs value={active} onValueChange={setActive} className="flex h-full min-h-0 flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-border pb-2">
          <div className="scroll-thin flex items-center gap-0.5 overflow-x-auto">
            <TabsList>
              {files.map((f) => (
                <TabsTrigger key={f.path} value={f.path}>
                  <FileCode2 className="h-3 w-3 shrink-0" />
                  <span className="font-mono">{f.path}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {loading && (
            <span className="flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground">
              <RefreshCw className="h-3 w-3 animate-spin" />
              syncing
            </span>
          )}
        </div>

        <div className="min-h-0 flex-1 pt-2">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-[13px] text-destructive">
              {error}
            </div>
          ) : loading && isEmpty ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : (
            files.map((f) => (
              <TabsContent key={f.path} value={f.path} className="h-full">
                <pre className="scroll-thin h-full max-h-[60vh] overflow-auto rounded-md border border-border bg-muted/30 p-3.5 text-[12px] leading-[1.65] lg:max-h-none">
                  <code className="font-mono">{f.content}</code>
                </pre>
              </TabsContent>
            ))
          )}
          {!loading && !error && !current && isEmpty && (
            <p className="py-8 text-center text-[13px] text-muted-foreground">
              Preview will appear here.
            </p>
          )}
        </div>
      </Tabs>
    </div>
  );
}
