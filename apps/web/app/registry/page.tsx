import { InstalledSkillList } from "@/components/InstalledSkillList";

export default function RegistryPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Registry</h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          All skills installed into <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">~/.skillforge/skills</code>
        </p>
      </div>
      {/* InstalledSkillList fetches on mount */}
      <InstalledSkillList variant="full" />
    </div>
  );
}
