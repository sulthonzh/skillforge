"use client";

import * as React from "react";
import { api } from "./api";

/**
 * Fetch and cache the actual configured local paths (skills_dir, config_path).
 * Falls back to the conventional default if the backend is unreachable, so the
 * UI never shows a blank where a path should be.
 */
const FALLBACK_SKILLS_DIR = "~/.skillforge/skills";

export function useSkillsDir(): string {
  const [dir, setDir] = React.useState(FALLBACK_SKILLS_DIR);
  React.useEffect(() => {
    let cancelled = false;
    api
      .getPaths()
      .then((p) => !cancelled && p.skills_dir && setDir(p.skills_dir))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return dir;
}
