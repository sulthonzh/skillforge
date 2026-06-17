import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Logo } from "@/components/Logo";
import { ToastProvider } from "@/components/ui/toast";
import { ThemeProvider, THEME_INIT_SCRIPT } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "SkillForge",
  description: "AI-powered local skill builder for engineers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* No-flash theme init: runs before paint so the correct theme class is
            on <html> from the first frame. Must be inline + synchronous. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>
          <ToastProvider>
            <div className="flex min-h-screen flex-col">
              <Header />
              <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-10">
                {children}
              </main>
              <Footer />
            </div>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Logo />
        </Link>
        <div className="flex items-center gap-3">
          <nav className="flex items-center gap-0.5 text-[13px]">
            <NavLink href="/" label="Build" />
            <NavLink href="/eval" label="Eval" />
            <NavLink href="/registry" label="Registry" />
            <NavLink href="/settings" label="Settings" />
          </nav>
          <div className="hidden sm:block">
            <ThemeToggle />
          </div>
        </div>
      </div>
      {/* Theme toggle accessible on mobile too, in a slim bar below the header */}
      <div className="flex justify-end px-4 pb-1.5 sm:hidden">
        <ThemeToggle />
      </div>
    </header>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      {label}
    </Link>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto w-full max-w-6xl px-4 py-5 text-center text-[11px] text-muted-foreground sm:px-6">
        SkillForge runs locally · Generated scripts are reference-only and never auto-executed
      </div>
    </footer>
  );
}
