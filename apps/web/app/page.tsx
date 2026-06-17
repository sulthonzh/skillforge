"use client";

import * as React from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { SkillManifestEditor } from "@/components/SkillManifestEditor";
import { SkillPreview } from "@/components/SkillPreview";
import { SkillInstallButton } from "@/components/SkillInstallButton";
import { InstalledSkillList } from "@/components/InstalledSkillList";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ChatPlanResponse, SkillManifest } from "@/lib/types";

export default function HomePage() {
  const [explanation, setExplanation] = React.useState<string | null>(null);
  const [manifest, setManifest] = React.useState<SkillManifest | null>(null);
  const [plannedAt, setPlannedAt] = React.useState<string | null>(null);

  function handlePlanned(result: ChatPlanResponse, _message: string) {
    setExplanation(result.explanation);
    setManifest(result.manifest);
    setPlannedAt(new Date().toLocaleTimeString());
  }

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Describe an engineering need</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          SkillForge recommends a specific, tool-driven stack — never a generic &quot;full-stack&quot;
          skill. Edit it, preview the files, then install locally.
        </p>
        <div className="mt-4">
          <ChatPanel onPlanned={handlePlanned} />
        </div>
      </section>

      {explanation && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>AI recommendation</CardTitle>
              {plannedAt && <Badge variant="outline">planned at {plannedAt}</Badge>}
            </div>
            <CardDescription>Review the rationale, then refine in the editor.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="scroll-thin whitespace-pre-wrap rounded-md bg-muted/40 p-3 text-xs leading-relaxed">
              {explanation}
            </pre>
          </CardContent>
        </Card>
      )}

      {manifest && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Skill manifest</CardTitle>
                <CardDescription>
                  Customize tools, workflow, and best practices before generating.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SkillManifestEditor manifest={manifest} onChange={setManifest} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Install</CardTitle>
                <CardDescription>
                  Writes the skill into <code className="text-xs">~/.skillforge/skills</code>.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SkillInstallButton manifest={manifest} />
              </CardContent>
            </Card>
          </section>
          <section className="lg:sticky lg:top-6 lg:h-[calc(100vh-7rem)]">
            <Card className="flex h-full flex-col">
              <CardHeader>
                <CardTitle>File preview</CardTitle>
                <CardDescription>Live render of the generated files.</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 overflow-hidden">
                <SkillPreview manifest={manifest} />
              </CardContent>
            </Card>
          </section>
        </div>
      )}

      <section>
        <Card>
          <CardHeader>
            <CardTitle>Installed skills</CardTitle>
            <CardDescription>Skills currently in your local registry.</CardDescription>
          </CardHeader>
          <CardContent>
            <InstalledSkillList />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
