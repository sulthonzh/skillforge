"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { InstalledSkill } from "@/lib/types";

// Static skill-detail page that reads the skill name from the query string
// (e.g. /skill?name=backend-fastapi-postgres). Kept as a static route so the
// whole app can be `output: "export"`-ed and served from FastAPI in one port.
//
// `useSearchParams` must be inside a <Suspense> boundary during prerender, so
// the page default export wraps the inner content in Suspense.

function SkillDetailContent() {
  const search = useSearchParams();
  const skillName = search.get("name") ?? "";
  const [skill, setSkill] = React.useState<InstalledSkill | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!skillName) {
      setError("No skill name provided. Open a skill from the registry.");
      return;
    }
    api
      .listSkills()
      .then((res) => {
        const found = res.skills.find((s) => s.name === skillName) ?? null;
        setSkill(found);
        if (!found) setError(`No installed skill named '${skillName}'.`);
      })
      .catch((e: ApiError) => setError(e.message));
  }, [skillName]);

  return (
    <>
      <div>
        <Link href="/registry" className="text-xs text-muted-foreground hover:underline">
          ← back to registry
        </Link>
        <h1 className="mt-1 font-mono text-2xl font-bold tracking-tight">
          {skillName || "Skill"}
        </h1>
      </div>

      {error && (
        <Card>
          <CardContent>
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {skill && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{skill.title || skill.name}</CardTitle>
              <Badge variant="secondary">v{skill.version}</Badge>
            </div>
            <CardDescription>{skill.domain}</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-3 gap-2 text-sm">
              <dt className="font-medium">Install path</dt>
              <dd className="col-span-2 break-all font-mono text-xs">{skill.path}</dd>
              <dt className="font-medium">Installed at</dt>
              <dd className="col-span-2 text-xs text-muted-foreground">
                {skill.installed_at ?? "—"}
              </dd>
            </dl>
            <div className="mt-4 flex gap-2">
              <Button
                variant="outline"
                onClick={async () => {
                  if (confirm(`Remove '${skill.name}'?`)) {
                    await api.removeSkill(skill.name);
                    window.location.href = "/registry";
                  }
                }}
              >
                Remove skill
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}

export default function SkillDetailPage() {
  return (
    <React.Suspense
      fallback={
        <p className="text-sm text-muted-foreground">Loading skill…</p>
      }
    >
      <div className="flex flex-col gap-4">
        <SkillDetailContent />
      </div>
    </React.Suspense>
  );
}
