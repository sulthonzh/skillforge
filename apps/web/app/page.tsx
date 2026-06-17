"use client";

import * as React from "react";
import { MessageSquare, Sliders, Eye } from "lucide-react";
import { ChatPanel } from "@/components/ChatPanel";
import { SkillManifestEditor } from "@/components/SkillManifestEditor";
import { SkillPreview } from "@/components/SkillPreview";
import { SkillInstallButton } from "@/components/SkillInstallButton";
import { InstalledSkillList } from "@/components/InstalledSkillList";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { ChatPlanResponse, SkillManifest } from "@/lib/types";

export default function HomePage() {
  const [explanation, setExplanation] = React.useState<string | null>(null);
  const [manifest, setManifest] = React.useState<SkillManifest | null>(null);
  const [mobileTab, setMobileTab] = React.useState("edit");

  function handlePlanned(result: ChatPlanResponse, _message: string) {
    setExplanation(result.explanation);
    setManifest(result.manifest);
    setMobileTab("edit");
  }

  return (
    <div className="flex flex-col gap-8">
      {/* ───────── Step 1 — Describe ───────── */}
      <section>
        <StepHeader step={1} title="Describe" subtitle="Tell SkillForge what you need to build" />
        <Card className="mt-3">
          <CardContent className="p-4 sm:p-5">
            <ChatPanel onPlanned={handlePlanned} />
          </CardContent>
        </Card>

        {/* Compact recent strip (empty state shows nothing) */}
        <div className="mt-3">
          <InstalledSkillList variant="compact" />
        </div>
      </section>

      {/* ───────── Step 2 — Review & edit ───────── */}
      {manifest && explanation && (
        <section className="sf-toast-in">
          <StepHeader
            step={2}
            title="Review & install"
            subtitle="Tune the stack, preview the files, then install locally"
          />

          {/* Mobile/tablet: tabs to switch between edit and preview.
              Desktop (lg+): side-by-side. */}
          <div className="mt-3 lg:hidden">
            <Tabs value={mobileTab} onValueChange={setMobileTab}>
              <TabsList className="w-full">
                <TabsTrigger value="edit" className="flex-1">
                  <Sliders className="h-3 w-3" /> Edit
                </TabsTrigger>
                <TabsTrigger value="preview" className="flex-1">
                  <Eye className="h-3 w-3" /> Preview
                </TabsTrigger>
              </TabsList>
              <TabsContent value="edit" className="mt-3">
                <ManifestColumn
                  manifest={manifest}
                  explanation={explanation}
                  onChange={setManifest}
                />
              </TabsContent>
              <TabsContent value="preview" className="mt-3">
                <PreviewColumn manifest={manifest} />
              </TabsContent>
            </Tabs>
          </div>

          <div className="mt-3 hidden gap-5 lg:grid lg:grid-cols-2">
            <div className="min-w-0">
              <ManifestColumn
                manifest={manifest}
                explanation={explanation}
                onChange={setManifest}
              />
            </div>
            <div className="min-w-0">
              <PreviewColumn manifest={manifest} />
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function StepHeader({
  step,
  title,
  subtitle,
}: {
  step: number;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-[12px] font-semibold text-primary-foreground">
        {step}
      </span>
      <div>
        <h2 className="text-[15px] font-semibold leading-tight tracking-tight">{title}</h2>
        <p className="text-[12px] text-muted-foreground">{subtitle}</p>
      </div>
    </div>
  );
}

function ManifestColumn({
  manifest,
  explanation,
  onChange,
}: {
  manifest: SkillManifest;
  explanation: string;
  onChange: (m: SkillManifest) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* AI explanation */}
      <div className="rounded-lg border border-border bg-muted/30 p-3.5">
        <div className="mb-1.5 flex items-center gap-1.5">
          <MessageSquare className="h-3.5 w-3.5 text-primary" />
          <span className="micro-label">AI recommendation</span>
        </div>
        <pre className="scroll-thin max-h-40 overflow-auto whitespace-pre-wrap font-sans text-[12px] leading-relaxed text-muted-foreground">
          {explanation}
        </pre>
      </div>

      <Card>
        <CardContent className="p-4 sm:p-5">
          <SkillManifestEditor manifest={manifest} onChange={onChange} />
        </CardContent>
      </Card>

      {/* Install */}
      <Card>
        <CardContent className="p-4 sm:p-5">
          <div className="mb-3">
            <h3 className="text-[14px] font-semibold tracking-tight">Install</h3>
            <p className="text-[12px] text-muted-foreground">
              Writes the skill into <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">~/.skillforge/skills</code>
            </p>
          </div>
          <SkillInstallButton manifest={manifest} />
        </CardContent>
      </Card>
    </div>
  );
}

function PreviewColumn({ manifest }: { manifest: SkillManifest }) {
  return (
    <Card className="flex h-full flex-col">
      <CardContent className="flex min-h-[400px] flex-1 flex-col p-4 sm:p-5">
        <div className="mb-1.5">
          <h3 className="text-[14px] font-semibold tracking-tight">File preview</h3>
          <p className="text-[12px] text-muted-foreground">Live render of the generated files</p>
        </div>
        <div className="min-h-0 flex-1">
          <SkillPreview manifest={manifest} />
        </div>
      </CardContent>
    </Card>
  );
}
