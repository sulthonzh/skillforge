"use client";

import * as React from "react";
import {
  Store,
  Upload,
  Search,
  KeyRound,
  CheckCircle2,
  XCircle,
  Star,
  Download,
  Trash2,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type { BridgeToken, InstalledSkill, MarketplaceListing, PendingApproval } from "@/lib/types";

export default function MarketplacePage() {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Store className="h-5 w-5 text-primary" />
          Marketplace
        </h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Browse, publish, and install skills. The local adapter lets you try the full flow offline today.
        </p>
      </div>
      <ApprovalQueue />
      <ConnectionPanel />
      <BrowsePanel />
      <PublishPanel />
    </div>
  );
}

// ---- Approval queue (marketplace-originated installs) ----

function ApprovalQueue() {
  const [pending, setPending] = React.useState<PendingApproval[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const { toast } = useToast();

  const refresh = React.useCallback(async () => {
    try {
      const r = await api.marketplacePending();
      setPending(r.pending);
    } catch {
      /* best-effort */
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
    const i = setInterval(refresh, 5000);
    return () => clearInterval(i);
  }, [refresh]);

  async function approve(id: string) {
    setBusy(id);
    try {
      await api.marketplaceApprove(id);
      toast({ variant: "success", title: "Skill installed" });
      refresh();
    } catch (e) {
      toast({ variant: "error", title: "Install failed", description: (e as ApiError).message });
    } finally {
      setBusy(null);
    }
  }

  async function reject(id: string) {
    setBusy(id);
    try {
      await api.marketplaceReject(id);
      refresh();
    } finally {
      setBusy(null);
    }
  }

  if (loading || pending.length === 0) return null;

  return (
    <Card className="border-primary/30 bg-accent/20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <Download className="h-4 w-4 text-primary" />
          Pending installs ({pending.length})
        </CardTitle>
        <CardDescription>Approve or reject skills from the marketplace.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {pending.map((a) => (
          <div key={a.id} className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2">
            <div>
              <span className="font-mono text-[13px] font-medium">{a.skill_name}</span>
              <span className="ml-2 text-[11px] text-muted-foreground">from {a.source}</span>
            </div>
            <div className="flex gap-1.5">
              <Button size="xs" variant="success" onClick={() => approve(a.id)} loading={busy === a.id}>
                <CheckCircle2 className="h-3 w-3" /> Approve
              </Button>
              <Button size="xs" variant="ghost" className="text-destructive" onClick={() => reject(a.id)} disabled={busy === a.id}>
                <XCircle className="h-3 w-3" /> Reject
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ---- Connection (pairing codes + token management) ----

function ConnectionPanel() {
  const [tokens, setTokens] = React.useState<BridgeToken[]>([]);
  const [code, setCode] = React.useState<string | null>(null);
  const [generating, setGenerating] = React.useState(false);
  const { toast } = useToast();

  const refreshTokens = React.useCallback(async () => {
    try {
      setTokens((await api.marketplaceTokens()).tokens);
    } catch {
      /* best-effort */
    }
  }, []);

  React.useEffect(() => {
    refreshTokens();
  }, [refreshTokens]);

  async function generate() {
    setGenerating(true);
    try {
      const r = await api.marketplacePairCode();
      setCode(r.code);
      toast({ variant: "info", title: "Pairing code generated", description: `Enter ${r.code} on the marketplace site.` });
    } finally {
      setGenerating(false);
    }
  }

  async function revoke(id: string) {
    try {
      await api.marketplaceRevokeToken(id);
      refreshTokens();
      toast({ variant: "success", title: "Token revoked" });
    } catch (e) {
      toast({ variant: "error", title: "Revoke failed", description: (e as ApiError).message });
    }
  }

  const active = tokens.filter((t) => !t.revoked);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <KeyRound className="h-4 w-4 text-muted-foreground" />
          Connection
        </CardTitle>
        <CardDescription>
          Pair the SkillForge Marketplace site with this local instance.
          {active.length > 0 && <Badge variant="success" className="ml-2">{active.length} connected</Badge>}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={generate} loading={generating}>
            <KeyRound className="h-3.5 w-3.5" /> Generate pairing code
          </Button>
          {code && (
            <div className="flex items-center gap-2 rounded-md border border-primary/30 bg-accent px-3 py-2">
              <span className="micro-label">Code</span>
              <code className="font-mono text-lg font-bold tracking-[0.3em] text-primary">{code}</code>
              <span className="text-[11px] text-muted-foreground">expires in 10 min</span>
            </div>
          )}
        </div>
        {tokens.length > 0 && (
          <div>
            <span className="micro-label mb-2 block">Bridge tokens</span>
            <ul className="flex flex-col gap-1.5">
              {tokens.map((t) => (
                <li key={t.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5">
                  <span className="font-mono text-[11px]">{t.label}</span>
                  <div className="flex flex-wrap gap-1">
                    {t.scopes.map((s) => (
                      <Badge key={s} variant="mono">{s}</Badge>
                    ))}
                  </div>
                  {t.revoked ? (
                    <Badge variant="outline">revoked</Badge>
                  ) : (
                    <Button size="xs" variant="ghost" className="ml-auto text-destructive" onClick={() => revoke(t.id)}>
                      <Trash2 className="h-3 w-3" /> Revoke
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---- Browse ----

function BrowsePanel() {
  const [q, setQ] = React.useState("");
  const [results, setResults] = React.useState<MarketplaceListing[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [installing, setInstalling] = React.useState<string | null>(null);
  const { toast } = useToast();

  async function search() {
    setLoading(true);
    try {
      const r = await api.marketplaceSearch(q);
      setResults(r.results);
    } catch (e) {
      toast({ variant: "error", title: "Search failed", description: (e as ApiError).message });
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function install(listing: MarketplaceListing) {
    setInstalling(listing.id);
    try {
      const r = await api.marketplaceInstall(listing.id);
      toast({
        variant: "info",
        title: "Queued for approval",
        description: `${listing.name} is ready to install — approve it above.`,
      });
    } catch (e) {
      toast({ variant: "error", title: "Install failed", description: (e as ApiError).message });
    } finally {
      setInstalling(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <Search className="h-4 w-4 text-muted-foreground" /> Browse
        </CardTitle>
        <CardDescription>Search skills published to the marketplace.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex gap-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="Search skills…" />
          <Button variant="outline" onClick={search} loading={loading}>
            <Search className="h-3.5 w-3.5" /> Search
          </Button>
        </div>
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : results.length === 0 ? (
          <p className="py-4 text-center text-[13px] text-muted-foreground">
            No skills found. Publish one below to populate the marketplace.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {results.map((l) => (
              <li key={l.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-card p-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[13px] font-medium">{l.name}</span>
                    <Badge variant="mono">v{l.version}</Badge>
                    {l.free ? <Badge variant="success">free</Badge> : <Badge variant="warning">${l.price_usd}</Badge>}
                    {l.rating > 0 && (
                      <span className="flex items-center gap-0.5 text-[11px] text-muted-foreground">
                        <Star className="h-3 w-3 fill-warning text-warning" /> {l.rating.toFixed(1)}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-[12px] text-muted-foreground">{l.description || l.title}</p>
                  <p className="text-[11px] text-muted-foreground">by {l.author} · {l.downloads} downloads</p>
                </div>
                <Button size="sm" variant="outline" onClick={() => install(l)} loading={installing === l.id}>
                  <Download className="h-3.5 w-3.5" /> Install
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---- Publish ----

function PublishPanel() {
  const [skills, setSkills] = React.useState<InstalledSkill[]>([]);
  const [skillName, setSkillName] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [tags, setTags] = React.useState("");
  const [price, setPrice] = React.useState("0");
  const [publishing, setPublishing] = React.useState(false);
  const { toast } = useToast();

  React.useEffect(() => {
    api.listSkills().then((r) => {
      setSkills(r.skills);
      if (r.skills[0]) setSkillName(r.skills[0].name);
    }).catch(() => {});
  }, []);

  async function publish() {
    if (!skillName) return;
    setPublishing(true);
    try {
      const r = await api.marketplacePublish({
        skill_name: skillName,
        title,
        description,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        price_usd: parseFloat(price) || 0,
      });
      toast({ variant: "success", title: "Published", description: `${r.listing.name} v${r.listing.version} is now listed.` });
    } catch (e) {
      toast({ variant: "error", title: "Publish failed", description: (e as ApiError).message });
    } finally {
      setPublishing(false);
    }
  }

  if (skills.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-[13px] text-muted-foreground">
          Install a skill locally before publishing.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <Upload className="h-4 w-4 text-muted-foreground" /> Publish
        </CardTitle>
        <CardDescription>Package a local skill and list it on the marketplace (free or paid).</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className="micro-label">Skill</span>
            <select value={skillName} onChange={(e) => setSkillName(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
              {skills.map((s) => <option key={s.name} value={s.name}>{s.name} (v{s.version})</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="micro-label">Title</span>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Display title" />
          </label>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="micro-label">Description</span>
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="What does this skill do?" />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className="micro-label">Tags (comma-separated)</span>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="backend, python" />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="micro-label">Price (USD, 0 = free)</span>
            <Input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className="font-mono" />
          </label>
        </div>
        <div>
          <Button onClick={publish} loading={publishing} disabled={!skillName}>
            {!publishing && <Upload className="h-3.5 w-3.5" />} Publish skill
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
