"use client";

import * as React from "react";
import { Wrench, Play, Eye, CheckCircle2, XCircle, Loader2, Terminal } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { useToast } from "./ui/toast";
import { api, ApiError } from "@/lib/api";
import type { ToolPreview, ToolRunResult } from "@/lib/types";

export function ToolsPanel({ skillName }: { skillName: string }) {
  const [tools, setTools] = React.useState<ToolPreview[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [previewing, setPreviewing] = React.useState<string | null>(null);
  const [running, setRunning] = React.useState<string | null>(null);
  const [output, setOutput] = React.useState<ToolRunResult | null>(null);
  const [confirming, setConfirming] = React.useState<string | null>(null);
  const { toast } = useToast();

  const refresh = React.useCallback(async () => {
    try {
      setTools(await api.listSkillTools(skillName));
    } catch {
      /* best-effort */
    } finally {
      setLoading(false);
    }
  }, [skillName]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function preview(tool: ToolPreview) {
    setPreviewing(tool.script);
    setOutput(null);
    try {
      const p = await api.previewTool(skillName, tool.script);
      toast({ variant: p.runnable ? "info" : "error", title: tool.script, description: p.runnable ? p.command.join(" ") : p.reason });
    } catch (e) {
      toast({ variant: "error", title: "Preview failed", description: (e as ApiError).message });
    } finally {
      setPreviewing(null);
    }
  }

  async function run(tool: ToolPreview) {
    setRunning(tool.script);
    setOutput(null);
    try {
      const result = await api.runTool(skillName, tool.script, true);
      setOutput(result);
      toast({
        variant: result.exit_code === 0 ? "success" : "error",
        title: `${tool.script} → exit ${result.exit_code}${result.timed_out ? " (timeout)" : ""}`,
      });
    } catch (e) {
      toast({ variant: "error", title: "Run failed", description: (e as ApiError).message });
    } finally {
      setRunning(null);
      setConfirming(null);
    }
  }

  if (loading) return null;
  if (tools.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <Wrench className="h-4 w-4 text-muted-foreground" />
          Generated tools ({tools.length})
        </CardTitle>
        <CardDescription>
          Real, runnable helper scripts. Preview before running — execution requires your consent.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {tools.map((t) => (
          <div key={t.script} className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2">
            <div className="flex items-center gap-2 min-w-0">
              <Terminal className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <code className="truncate font-mono text-[12px]">{t.script}</code>
              {t.runnable ? (
                <Badge variant="success">runnable</Badge>
              ) : (
                <Badge variant="outline">ref</Badge>
              )}
            </div>
            <div className="flex shrink-0 gap-1.5">
              <Button size="xs" variant="ghost" onClick={() => preview(t)} loading={previewing === t.script} disabled={!t.runnable}>
                <Eye className="h-3 w-3" /> Preview
              </Button>
              {confirming === t.script ? (
                <Button size="xs" variant="destructive" onClick={() => run(t)} loading={running === t.script}>
                  Confirm run
                </Button>
              ) : (
                <Button size="xs" variant="outline" onClick={() => setConfirming(t.script)} disabled={!t.runnable || running !== null}>
                  <Play className="h-3 w-3" /> Run
                </Button>
              )}
            </div>
          </div>
        ))}

        {/* Output viewer */}
        {output && (
          <div className="mt-2 rounded-md border border-border bg-muted/30 p-3">
            <div className="mb-1.5 flex items-center gap-2">
              {output.exit_code === 0 ? (
                <CheckCircle2 className="h-4 w-4 text-success" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              <span className="text-[12px] font-medium">
                Exit {output.exit_code}{output.timed_out ? " · timed out" : ""}
              </span>
              <code className="truncate font-mono text-[11px] text-muted-foreground">{output.command.join(" ")}</code>
            </div>
            {output.stdout && (
              <pre className="scroll-thin max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted-foreground">
                {output.stdout}
              </pre>
            )}
            {output.stderr && (
              <pre className="scroll-thin mt-1 max-h-32 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-destructive/80">
                {output.stderr}
              </pre>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
