"use client";

import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme, type ThemePref } from "./theme-provider";

// A compact 3-way segmented control: system (default) · light · dark.
// Shows the active state; click to switch. Fits in the header.

const OPTIONS: { value: ThemePref; label: string; icon: typeof Sun }[] = [
  { value: "system", label: "System", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

export function ThemeToggle() {
  const { pref, setPref } = useTheme();
  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted/40 p-0.5"
      role="group"
      aria-label="Theme"
      title={`Theme: ${pref}`}
    >
      {OPTIONS.map((opt) => {
        const active = pref === opt.value;
        const Icon = opt.icon;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => setPref(opt.value)}
            aria-pressed={active}
            title={`${opt.label} theme`}
            className={`inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors ${
              active
                ? "bg-card text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        );
      })}
    </div>
  );
}
