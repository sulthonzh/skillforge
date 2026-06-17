"use client";

import * as React from "react";

// SkillForge theme: "system" follows the OS preference (prefers-color-scheme),
// resolving to either "dark" or "light". The resolved value is what gets the
// `dark` class on <html>; the *preference* (system/dark/light) is what's stored.

export type ThemePref = "system" | "dark" | "light";

interface ThemeCtx {
  pref: ThemePref;
  resolved: "dark" | "light";
  setPref: (p: ThemePref) => void;
  cycle: () => void;
}

const Ctx = React.createContext<ThemeCtx | null>(null);
const STORAGE_KEY = "skillforge-theme";

function systemResolved(): "dark" | "light" {
  if (typeof window === "undefined") return "dark"; // SSR default — dark-first
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyClass(resolved: "dark" | "light") {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // SSR renders dark (matches the no-flash script's default). The script then
  // corrects to the user's stored pref before paint.
  const [pref, setPrefState] = React.useState<ThemePref>("system");
  const [resolved, setResolved] = React.useState<"dark" | "light">("dark");

  // On mount, read the stored preference (the inline script already set the
  // class; we sync React state to it).
  React.useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as ThemePref | null) ?? "system";
    setPrefState(stored);
    const res = stored === "system" ? systemResolved() : stored;
    setResolved(res);
    applyClass(res);
  }, []);

  // Follow OS changes when in "system" mode.
  React.useEffect(() => {
    if (pref !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const res = systemResolved();
      setResolved(res);
      applyClass(res);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [pref]);

  const setPref = React.useCallback((p: ThemePref) => {
    setPrefState(p);
    localStorage.setItem(STORAGE_KEY, p);
    const res = p === "system" ? systemResolved() : p;
    setResolved(res);
    applyClass(res);
  }, []);

  const cycle = React.useCallback(() => {
    const order: ThemePref[] = ["system", "light", "dark"];
    const idx = order.indexOf(pref);
    setPref(order[(idx + 1) % order.length]);
  }, [pref, setPref]);

  return (
    <Ctx.Provider value={{ pref, resolved, setPref, cycle }}>{children}</Ctx.Provider>
  );
}

export function useTheme(): ThemeCtx {
  const ctx = React.useContext(Ctx);
  if (!ctx) {
    // Safe fallback for components rendered outside the provider.
    return {
      pref: "system",
      resolved: "dark",
      setPref: () => {},
      cycle: () => {},
    };
  }
  return ctx;
}

/**
 * Inline script injected into <head>. Runs synchronously before paint so the
 * correct theme class is on <html> from the first frame — no flash of the wrong
 * theme. Kept as a string so it's not parsed by React.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var k='${STORAGE_KEY}';var p=localStorage.getItem(k)||'system';var d=p==='dark'||(p==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);var r=document.documentElement;r.classList.toggle('dark',d);r.style.colorScheme=d?'dark':'light';}catch(e){}})();`;
