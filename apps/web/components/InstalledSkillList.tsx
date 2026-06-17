"use client";

import * as React from "react";
import { Trash2, RefreshCw, ArrowRight, Package } from "lucide-react";
import Link from "next/link";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { api, ApiError } from "@/lib/api";
import { useToast } from "./ui/toast";
import { Skeleton } from "./ui/skeleton";
import type { InstalledSkill } from "@/lib/types";

export function InstalledSkillList({ variant = "full" }: { variant?: "full" | "compact" }) {
  const [skills, setSkills] = React.useState<InstalledSkill[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const { toast } = useToast();

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSkills((await api.listSkills()).skills);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function remove(name: string) {
    if (!confirm(`Remove installed skill '${name}'? This deletes its files.`)) return;
    try {
      await api.removeSkill(name);
      setSkills((prev) => prev.filter((s) => s.name !== name));
      toast({ variant: "success", title: `Removed ${name}` });
    } catch (e) {
      toast({ variant: "error", title: "Remove failed", description: (e as ApiError).message });
    }
  }

  // ---- loading ----
  if (loading) {
    if (variant === "compact") {
      return (
        <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
          <Skeleton className="h-3 w-32" />
        </div>
      );
    }
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  // ---- error ----
  if (error) {
    return (
      <p className="text-[13px] text-destructive">
        Could not load skills: {error}. Is the backend running?
      </p>
    );
  }

  // ---- empty ----
  if (skills.length === 0) {
    if (variant === "compact") return null;
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border py-10 text-center">
        <Package className="h-6 w-6 text-muted-foreground/50" />
        <p className="text-[13px] text-muted-foreground">
          No skills installed yet. Plan one above and click{" "}
          <span className="font-medium text-foreground">Install skill</span>.
        </p>
      </div>
    );
  }

  // ---- compact: a quiet "recent" strip (home page) ----
  if (variant === "compact") {
    const recent = skills.slice(0, 4);
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="micro-label mr-1">Recent</span>
        {recent.map((s) => (
          <Link
            key={s.name}
            href={`/skill?name=${encodeURIComponent(s.name)}`}
            className="group inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-[11px] transition-colors hover:border-primary/30 hover:bg-accent"
          >
            <span className="font-mono text-foreground">{s.name}</span>
            <span className="text-muted-foreground group-hover:text-accent-foreground">v{s.version}</span>
          </Link>
        ))}
        <Link
          href="/registry"
          className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    );
  }

  // ---- full list (registry page) ----
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted-foreground">{skills.length} installed</p>
        <Button size="xs" variant="ghost" onClick={refresh}>
          <RefreshCw className="h-3 w-3" />
          Refresh
        </Button>
      </div>
      <ul className="flex flex-col gap-1.5">
        {skills.map((s) => (
          <li
            key={s.name}
            className="group flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5 transition-colors hover:border-border/80"
          >
            <Package className="h-4 w-4 shrink-0 text-muted-foreground/50" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <a
                  href={`/skill?name=${encodeURIComponent(s.name)}`}
                  className="truncate font-mono text-[13px] font-medium text-foreground hover:text-primary"
                >
                  {s.name}
                </a>
                <Badge variant="mono">v{s.version}</Badge>
              </div>
              <p className="truncate text-[11px] text-muted-foreground">{s.domain}</p>
            </div>
            <code
              className="hidden max-w-[40%] truncate font-mono text-[10px] text-muted-foreground/70 sm:block"
              title={s.path}
            >
              {s.path}
            </code>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0 text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
              onClick={() => remove(s.name)}
              title="Remove"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
