"use client";

import * as React from "react";
import { Link2, Link2Off, RefreshCw, CheckCircle2, Copy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { useToast } from "./ui/toast";
import { api, ApiError } from "@/lib/api";
import type { DeployStatus } from "@/lib/types";

export function DeployPanel({ skillName }: { skillName: string }) {
  const [statuses, setStatuses] = React.useState<DeployStatus[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [deploying, setDeploying] = React.useState(false);
  const { toast } = useToast();

  const refresh = React.useCallback(async () => {
    try {
      const r = await api.deployStatus(skillName);
      setStatuses(r.targets);
    } catch {
      /* best-effort */
    } finally {
      setLoading(false);
    }
  }, [skillName]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function deployAll() {
    setDeploying(true);
    try {
      const r = await api.deploySymlink(skillName);
      const ok = r.deployments.filter((d: any) => d.status === "deployed").length;
      const failed = r.deployments.filter((d: any) => d.status === "failed").length;
      toast({
        variant: ok > 0 ? "success" : "error",
        title: `Deployed to ${ok} tool(s)${failed ? `, ${failed} failed` : ""}`,
      });
      refresh();
    } catch (e) {
      toast({ variant: "error", title: "Deploy failed", description: (e as ApiError).message });
    } finally {
      setDeploying(false);
    }
  }

  async function deployOne(target: string, method: string) {
    setDeploying(true);
    try {
      await api.deploySymlink(skillName, target, method);
      toast({ variant: "success", title: `Deployed to ${target}` });
      refresh();
    } catch (e) {
      toast({ variant: "error", title: "Deploy failed", description: (e as ApiError).message });
    } finally {
      setDeploying(false);
    }
  }

  async function undeployOne(target: string) {
    try {
      await api.undeploy(skillName, target);
      toast({ variant: "success", title: `Removed from ${target}` });
      refresh();
    } catch (e) {
      toast({ variant: "error", title: "Undeploy failed", description: (e as ApiError).message });
    }
  }

  if (loading) return null;
  const installed = statuses.filter((s) => s.tool_installed);
  const deployed = installed.filter((s) => s.deployed);

  if (installed.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-[15px]">
              <Link2 className="h-4 w-4 text-muted-foreground" />
              Deploy to AI tools
            </CardTitle>
            <CardDescription>
              Symlink this skill to your coding tools — one source of truth.
              {deployed.length > 0 && <Badge variant="success" className="ml-2">{deployed.length} active</Badge>}
            </CardDescription>
          </div>
          <div className="flex gap-1.5">
            <Button size="sm" onClick={deployAll} loading={deploying}>
              <Link2 className="h-3.5 w-3.5" /> Deploy to all
            </Button>
            <Button size="sm" variant="ghost" onClick={refresh}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-1.5">
          {installed.map((s) => (
            <li
              key={s.target}
              className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                {s.deployed ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                ) : (
                  <Link2 className="h-4 w-4 shrink-0 text-muted-foreground/40" />
                )}
                <div className="min-w-0">
                  <span className="text-[13px] font-medium">{s.label}</span>
                  {s.deployed && (
                    <>
                      <Badge variant="mono" className="ml-2">{s.method}</Badge>
                      <code className="ml-2 truncate font-mono text-[10px] text-muted-foreground">{s.path}</code>
                    </>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 gap-1">
                {s.deployed ? (
                  <>
                    <Button size="xs" variant="ghost" onClick={() => deployOne(s.target, "copy")} disabled={deploying}>
                      <Copy className="h-3 w-3" /> Copy
                    </Button>
                    <Button size="xs" variant="ghost" className="text-destructive" onClick={() => undeployOne(s.target)}>
                      <Link2Off className="h-3 w-3" /> Remove
                    </Button>
                  </>
                ) : (
                  <Button size="xs" variant="outline" onClick={() => deployOne(s.target, "symlink")} disabled={deploying}>
                    <Link2 className="h-3 w-3" /> Symlink
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
