"use client";

import * as React from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { api, ApiError } from "@/lib/api";
import type { InstalledSkill } from "@/lib/types";

export function InstalledSkillList() {
  const [skills, setSkills] = React.useState<InstalledSkill[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listSkills();
      setSkills(res.skills);
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
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading installed skills…</p>;
  if (error)
    return (
      <p className="text-sm text-destructive">
        Could not load skills: {error}. Is the backend running on :8000?
      </p>
    );
  if (skills.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No skills installed yet. Plan one above and click <strong>Install Skill</strong>.
      </p>
    );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Installed skills ({skills.length})</h3>
        <Button size="sm" variant="ghost" onClick={refresh}>
          Refresh
        </Button>
      </div>
      <ul className="flex flex-col gap-2">
        {skills.map((s) => (
          <li
            key={s.name}
            className="flex items-start justify-between gap-3 rounded-md border border-border bg-card p-3"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <a
                  href={`/skill?name=${encodeURIComponent(s.name)}`}
                  className="truncate font-mono text-sm font-medium text-primary hover:underline"
                >
                  {s.name}
                </a>
                <Badge variant="secondary">v{s.version}</Badge>
              </div>
              <p className="truncate text-xs text-muted-foreground">{s.domain}</p>
              <p className="truncate font-mono text-xs text-muted-foreground">{s.path}</p>
            </div>
            <Button size="sm" variant="ghost" className="text-destructive" onClick={() => remove(s.name)}>
              Remove
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
