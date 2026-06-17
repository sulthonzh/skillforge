import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { InstalledSkillList } from "@/components/InstalledSkillList";

export default function RegistryPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Skill Registry</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          All skills installed by SkillForge into <code className="text-xs">~/.skillforge/skills</code>.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Installed skills</CardTitle>
          <CardDescription>Remove a skill to delete its files and registry entry.</CardDescription>
        </CardHeader>
        <CardContent>
          {/* InstalledSkillList is a client component — fetches on mount. */}
          <InstalledSkillList />
        </CardContent>
      </Card>
    </div>
  );
}
