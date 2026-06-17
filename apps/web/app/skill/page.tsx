"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Package, Trash2, CheckCircle2, Pencil } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToolsPanel } from "@/components/ToolsPanel";
import { DeployPanel } from "@/components/DeployPanel";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type { InstalledSkill } from "@/lib/types";

function SkillDetailContent() {
  const search = useSearchParams();
  const skillName = search.get("name") ?? "";
  const [skill, setSkill] = React.useState<InstalledSkill | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const { toast } = useToast();

  React.useEffect(() => {
    if (!skillName) {
      setError("No skill name provided. Open a skill from the registry.");
      setLoading(false);
      return;
    }
    api
      .listSkills()
      .then((res) => {
        const found = res.skills.find((s) => s.name === skillName) ?? null;
        setSkill(found);
        if (!found) setError(`No installed skill named '${skillName}'.`);
      })
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, [skillName]);

  async function remove() {
    if (!skill || !confirm(`Remove '${skill.name}'?`)) return;
    try {
      await api.removeSkill(skill.name);
      toast({ variant: "success", title: `Removed ${skill.name}` });
      window.location.href = "/registry";
    } catch (e) {
      toast({ variant: "error", title: "Remove failed", description: (e as ApiError).message });
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <>
      <div>
        <Link
          href="/registry"
          className="inline-flex items-center gap-1 text-[12px] text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to registry
        </Link>
      </div>

      {error ? (
        <Card>
          <CardContent className="p-5">
            <p className="text-[13px] text-destructive">{error}</p>
          </CardContent>
        </Card>
      ) : skill ? (
        <>
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <Package className="h-5 w-5 text-muted-foreground" />
                <div>
                  <CardTitle className="font-mono text-[15px]">{skill.name}</CardTitle>
                  <CardDescription>{skill.domain}</CardDescription>
                </div>
              </div>
              <Badge variant="mono">v{skill.version}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-[auto_1fr]">
              <dt className="micro-label pt-1.5">Install path</dt>
              <dd>
                <code className="block break-all rounded-md border border-border bg-muted/40 px-2.5 py-2 font-mono text-[12px]">
                  {skill.path}
                </code>
              </dd>
              <dt className="micro-label pt-1.5">Installed</dt>
              <dd className="flex items-center gap-1.5 pt-1.5 text-[13px] text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                {skill.installed_at ? new Date(skill.installed_at).toLocaleString() : "—"}
              </dd>
            </dl>
            <div className="mt-5 flex flex-wrap gap-2">
              <Link href={`/?edit=${encodeURIComponent(skill.name)}`}>
                <Button>
                  <Pencil className="h-3.5 w-3.5" />
                  Edit skill
                </Button>
              </Link>
              <Button variant="outline" onClick={remove}>
                <Trash2 className="h-3.5 w-3.5" />
                Remove skill
              </Button>
            </div>
          </CardContent>
        </Card>
        <ToolsPanel skillName={skill.name} />
        <DeployPanel skillName={skill.name} />
      </>
      ) : null}
    </>
  );
}

export default function SkillDetailPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <div className="flex flex-col gap-4">
        <SkillDetailContent />
      </div>
    </React.Suspense>
  );
}
