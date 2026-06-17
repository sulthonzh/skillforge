import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "SkillForge",
  description: "AI-powered local skill builder for engineers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <header className="border-b border-border bg-card/50 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-lg">⚒️</span>
              <span className="text-lg font-bold tracking-tight">SkillForge</span>
              <span className="hidden text-xs text-muted-foreground sm:inline">
                · AI-powered local skill builder for engineers
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <Link
                href="/"
                className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Build
              </Link>
              <Link
                href="/registry"
                className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Registry
              </Link>
              <Link
                href="/settings"
                className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Settings
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
        <footer className="mx-auto max-w-7xl px-6 py-8 text-center text-xs text-muted-foreground">
          SkillForge runs locally. Generated scripts are reference-only and never auto-executed.
        </footer>
      </body>
    </html>
  );
}
